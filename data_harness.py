"""
Data Cleaning Pipeline — Diabetes 130-US Hospitals Dataset
===========================================================
References:
  [1] Strack, B. et al. (2014). Impact of HbA1c Measurement on Hospital Readmission
      Rates: Analysis of 70,000 Clinical Database Patient Records.
      BioMed Research International, 2014, Article 781670.
      https://doi.org/10.1155/2014/781670

  [2] Kuhn, M., & Johnson, K. (2013). Applied Predictive Modeling (pp. 43-47).
      Springer New York. ISBN 978-1-4614-6848-6.
      (Near-Zero Variance criterion: FR > 20 AND UP < 10%)

  [3] Pedregosa, F. et al. (2011). Scikit-learn: Machine Learning in Python.
      Journal of Machine Learning Research, 12, 2825-2830.
      (VarianceThreshold: sigma^2 = p*(1-p), threshold = p0*(1-p0) where p0=0.95)
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

try:
    from xgboost import XGBClassifier
except ImportError:
    XGBClassifier = None

# ============================================================
# NEAR-ZERO VARIANCE (NZV) DETECTOR
# Reference: Kuhn & Johnson (2013), Applied Predictive Modeling
# ============================================================
def compute_nzv(series, fr_threshold=20.0, up_threshold=10.0, var_threshold_p0=0.95):
    """
    Identify Near-Zero Variance features using two complementary criteria.

    Criterion A — Frequency Ratio (FR):
        FR = count(most_common) / count(second_most_common)
        If FR > fr_threshold  → dominated by a single value

    Criterion B — Uniqueness Percentage (UP):
        UP = (n_unique / n_total) * 100
        If UP < up_threshold  → too little diversity

    A feature is NZV if (FR > fr_threshold AND UP < up_threshold).

    Additionally, the Variance Threshold from scikit-learn is applied:
        sigma^2 = p * (1 - p),  where p = proportion of dominant class
        threshold t = p0 * (1 - p0) = 0.95 * 0.05 = 0.0475
        If sigma^2 < t → also flagged for removal.

    Returns a dict with all diagnostic metrics and the final boolean flag.
    """
    vc = series.dropna().value_counts()
    n_total = len(series.dropna())
    n_unique = len(vc)

    if n_unique == 0:
        return {'fr': float('inf'), 'up': 0.0, 'variance': 0.0, 'is_nzv': True,
                'below_var_thresh': True, 'dominant_p': 1.0}

    dominant_count = vc.iloc[0]
    second_count   = vc.iloc[1] if n_unique > 1 else 0

    fr       = dominant_count / second_count if second_count > 0 else float('inf')
    up       = (n_unique / n_total) * 100
    dominant_p = dominant_count / n_total
    variance = dominant_p * (1 - dominant_p)

    var_threshold = var_threshold_p0 * (1 - var_threshold_p0)   # 0.0475

    is_nzv            = (fr > fr_threshold) and (up < up_threshold)
    below_var_thresh   = variance < var_threshold

    return {
        'fr':               round(fr, 2),
        'up':               round(up, 4),
        'variance':         round(variance, 6),
        'dominant_p':       round(dominant_p, 6),
        'is_nzv':           is_nzv,
        'below_var_thresh': below_var_thresh,
        'drop':             is_nzv or below_var_thresh
    }


# ============================================================
# MEDICATION COLUMNS
# ============================================================
ALL_MED_COLS = [
    'metformin', 'repaglinide', 'nateglinide', 'chlorpropamide', 'glimepiride',
    'acetohexamide', 'glipizide', 'glyburide', 'tolbutamide', 'pioglitazone',
    'rosiglitazone', 'acarbose', 'miglitol', 'troglitazone', 'tolazamide',
    'examide', 'citoglipton', 'insulin', 'glyburide-metformin',
    'glipizide-metformin', 'glimepiride-pioglitazone',
    'metformin-rosiglitazone', 'metformin-pioglitazone'
]

TERMINAL_DISCHARGE_IDS = [11, 13, 14, 19, 20, 21]
HIGH_MISSING_AND_ID_COLS = ['weight', 'payer_code', 'encounter_id', 'patient_nbr']


def map_icd9(val):
    """Map raw ICD-9 diagnosis codes to the 9 Strack/HCUP clinical groups."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return 'Other'

    s = str(val).strip()
    if not s or s.lower() in {'nan', 'unknown'}:
        return 'Other'
    if s.startswith(('V', 'E')):
        return 'Other'

    try:
        n = float(s)
    except ValueError:
        return 'Other'

    if 390 <= n <= 459 or n == 785:
        return 'Circulatory'
    if 460 <= n <= 519 or n == 786:
        return 'Respiratory'
    if 520 <= n <= 579 or n == 787:
        return 'Digestive'
    if np.floor(n) == 250:
        return 'Diabetes'
    if 800 <= n <= 999:
        return 'Injury'
    if 710 <= n <= 739:
        return 'Musculoskeletal'
    if 580 <= n <= 629 or n == 788:
        return 'Genitourinary'
    if 140 <= n <= 239:
        return 'Neoplasms'
    return 'Other'


def age_to_midpoint(val):
    age_map = {
        '[0-10)': 5, '[10-20)': 15, '[20-30)': 25, '[30-40)': 35,
        '[40-50)': 45, '[50-60)': 55, '[60-70)': 65, '[70-80)': 75,
        '[80-90)': 85, '[90-100)': 95,
    }
    return age_map.get(val, np.nan)


def add_medication_change_count(df):
    med_cols = [c for c in ALL_MED_COLS if c in df.columns]
    if not med_cols:
        df['num_medications_changed'] = 0
        return df
    df['num_medications_changed'] = df[med_cols].apply(
        lambda row: int(row.isin(['Up', 'Down']).sum()), axis=1
    )
    return df


def load_and_clean_data(file_path, verbose=True):
    """
    Full cleaning pipeline following Strack et al. (2014) and Kuhn & Johnson (2013).
    Returns (cleaned_df, nzv_report_dict)
    """
    if verbose:
        print("Loading data...")
    df = pd.read_csv(file_path, na_values=['?'], keep_default_na=False, low_memory=False)
    if verbose:
        print(f"  Original shape: {df.shape}")

    # ----------------------------------------------------------
    # PHASE 1: ROW-LEVEL FILTERING (Strack et al., 2014)
    # ----------------------------------------------------------
    # 1a. Keep only the first encounter per patient
    df = df.sort_values('encounter_id').drop_duplicates(subset=['patient_nbr'], keep='first')
    if verbose:
        print(f"  After first-encounter filter: {df.shape}")

    # 1b. Remove terminal discharges (cannot be readmitted)
    df = df[~df['discharge_disposition_id'].isin(TERMINAL_DISCHARGE_IDS)]
    if verbose:
        print(f"  After terminal discharge removal: {df.shape}")

    # 1c. Remove invalid gender (3 rows)
    df = df[df['gender'] != 'Unknown/Invalid']

    # ----------------------------------------------------------
    # PHASE 2: NZV-BASED MEDICATION COLUMN REMOVAL
    # Reference: Kuhn & Johnson (2013); Pedregosa et al. (2011)
    # ----------------------------------------------------------
    nzv_report = {}
    cols_to_drop = []

    for col in ALL_MED_COLS:
        if col not in df.columns:
            continue
        metrics = compute_nzv(df[col])
        nzv_report[col] = metrics
        if metrics['drop']:
            cols_to_drop.append(col)

    df = df.drop(columns=cols_to_drop)
    if verbose:
        print(f"\n  NZV: Dropped {len(cols_to_drop)} medication columns:")
        for c in cols_to_drop:
            m = nzv_report[c]
            print(f"    {c:<35} FR={m['fr']:>10.1f}  σ²={m['variance']:.5f}")
        kept = [c for c in ALL_MED_COLS if c in df.columns]
        print(f"  NZV: Kept {len(kept)} medication columns: {kept}")

    # ----------------------------------------------------------
    # PHASE 3: MISSING VALUE IMPUTATION (Cleaning — not Feature Eng.)
    # ----------------------------------------------------------
    # Replace '?' (now NaN) with informative categories
    if 'race' in df.columns:
        df['race'] = df['race'].fillna('Unknown')

    if 'medical_specialty' in df.columns:
        df['medical_specialty'] = df['medical_specialty'].fillna('Missing')

    for diag_col in ['diag_1', 'diag_2', 'diag_3']:
        if diag_col in df.columns:
            df[diag_col] = df[diag_col].fillna('Unknown')

    if verbose:
        print(f"\n  Final cleaned shape: {df.shape}")
        print(f"  Readmission rate (<30 days): {(df['readmitted'] == '<30').mean():.4f}")

    return df, nzv_report


def make_model_ready_data(cleaned_df, nzv_report=None, verbose=True):
    """
    Convert the cleaned clinical table into a fully model-ready design matrix:
    leakage/high-missing drops, ICD-9 grouping, age midpoint conversion, binary
    target, medication-change summary, train-safe imputation, scaling, and
    one-hot encoding.
    """
    df = cleaned_df.copy()

    # Feature engineering before medication-column removal preserves the signal
    # that a diabetic medication was actively adjusted during the encounter.
    df = add_medication_change_count(df)

    dropped_med_cols = []
    if nzv_report:
        dropped_med_cols = [col for col, metrics in nzv_report.items() if metrics.get('drop')]
        df = df.drop(columns=dropped_med_cols, errors='ignore')

    df = df.drop(columns=[c for c in HIGH_MISSING_AND_ID_COLS if c in df.columns], errors='ignore')

    if 'age' in df.columns:
        df['age'] = df['age'].apply(age_to_midpoint)

    for diag_col in ['diag_1', 'diag_2', 'diag_3']:
        if diag_col in df.columns:
            df[diag_col] = df[diag_col].apply(map_icd9)

    if 'readmitted' not in df.columns:
        raise ValueError("Expected target column 'readmitted' in cleaned dataframe.")
    df['readmitted'] = (df['readmitted'] == '<30').astype(int)

    numeric_cols = [c for c in df.columns if c != 'readmitted' and pd.api.types.is_numeric_dtype(df[c])]
    categorical_cols = [c for c in df.columns if c != 'readmitted' and c not in numeric_cols]

    try:
        onehot = OneHotEncoder(handle_unknown='ignore', sparse_output=False)
    except TypeError:
        onehot = OneHotEncoder(handle_unknown='ignore', sparse=False)

    preprocessor = ColumnTransformer(
        transformers=[
            ('num', Pipeline([
                ('imputer', SimpleImputer(strategy='median')),
                ('scaler', StandardScaler()),
            ]), numeric_cols),
            ('cat', Pipeline([
                ('imputer', SimpleImputer(strategy='most_frequent')),
                ('onehot', onehot),
            ]), categorical_cols),
        ],
        remainder='drop',
        verbose_feature_names_out=False,
    )

    X = df.drop(columns=['readmitted'])
    y = df['readmitted'].astype(int)
    X_encoded = preprocessor.fit_transform(X)
    feature_names = preprocessor.get_feature_names_out()
    model_ready = pd.DataFrame(X_encoded, columns=feature_names, index=df.index)
    model_ready.insert(0, 'readmitted', y.values)

    numeric_pipeline = {
        'columns': numeric_cols,
        'missing_strategy': 'SimpleImputer(strategy="median")',
        'normalization': 'StandardScaler',
        'normalization_formula': 'z = (x - training_mean) / training_standard_deviation',
        'why': 'Median imputation is robust to skew/outliers; z-score scaling keeps numeric magnitudes comparable for linear models.',
    }
    categorical_pipeline = {
        'columns': categorical_cols,
        'missing_strategy': 'SimpleImputer(strategy="most_frequent")',
        'encoding': 'OneHotEncoder(handle_unknown="ignore")',
        'why': 'One-hot encoding prevents numeric category IDs from being interpreted as ordinal distances; unknown future categories are ignored safely.',
    }
    clinical_feature_engineering = {
        'age': 'Age brackets such as [60-70) are converted to midpoint values such as 65 before scaling.',
        'icd9': 'diag_1, diag_2, and diag_3 are grouped into Circulatory, Respiratory, Digestive, Diabetes, Injury, Musculoskeletal, Genitourinary, Neoplasms, or Other.',
        'target': "readmitted is converted to binary: '<30' = 1, '>30' and 'NO' = 0.",
        'medication_complexity': "num_medications_changed counts medication columns marked 'Up' or 'Down' before near-zero variance medication columns are dropped.",
        'clinical_none_values': "A1Cresult='None' and max_glu_serum='None' are preserved as meaningful 'test not performed' categories.",
    }

    encoded_feature_groups = {}
    for col in categorical_cols:
        prefix = f'{col}_'
        encoded_feature_groups[col] = int(sum(name.startswith(prefix) for name in feature_names))

    transformations = [
        "Removed leakage/high-missing columns: weight, payer_code, encounter_id, patient_nbr.",
        "Converted age brackets to numeric midpoints.",
        "Grouped diag_1, diag_2, diag_3 ICD-9 codes into 9 clinical categories.",
        "Binarized target: readmitted '<30' = 1, '>30' and 'NO' = 0.",
        "Created num_medications_changed from Up/Down medication adjustments before NZV medication drops.",
        "Dropped near-zero variance medication columns identified by the cleaning audit.",
        "Median-imputed and standardized numeric features.",
        "Mode-imputed and one-hot encoded categorical features.",
    ]

    report = {
        'input_rows': int(len(cleaned_df)),
        'input_columns': int(cleaned_df.shape[1]),
        'model_ready_rows': int(model_ready.shape[0]),
        'model_ready_columns': int(model_ready.shape[1]),
        'positive_class_rate': round(float(y.mean()), 6),
        'numeric_columns_before_encoding': numeric_cols,
        'categorical_columns_before_encoding': categorical_cols,
        'dropped_columns': HIGH_MISSING_AND_ID_COLS + dropped_med_cols,
        'dropped_nzv_medications': dropped_med_cols,
        'numeric_pipeline': numeric_pipeline,
        'categorical_pipeline': categorical_pipeline,
        'clinical_feature_engineering': clinical_feature_engineering,
        'encoded_feature_groups': encoded_feature_groups,
        'transformations': transformations,
        'sample_columns': model_ready.columns[:30].tolist(),
        'sample_rows': model_ready.head(100).round(6).to_dict(orient='records'),
    }

    if verbose:
        print(f"  Model-ready shape: {model_ready.shape}")
        print(f"  Positive class rate: {y.mean():.4f}")

    return model_ready, report


def _evaluate_classifier(name, clf, X_train, X_test, y_train, y_test, feature_names, feature_mode):
    X_train_values = X_train.to_numpy()
    X_test_values = X_test.to_numpy()
    clf.fit(X_train_values, y_train)
    y_pred = clf.predict(X_test_values)
    if hasattr(clf, 'predict_proba'):
        y_score = clf.predict_proba(X_test_values)[:, 1]
    else:
        y_score = clf.decision_function(X_test_values)

    result = {
        'model_name': name,
        'feature_mode': feature_mode,
        'metrics': {
            'accuracy': round(float(accuracy_score(y_test, y_pred)), 6),
            'precision': round(float(precision_score(y_test, y_pred, zero_division=0)), 6),
            'recall': round(float(recall_score(y_test, y_pred, zero_division=0)), 6),
            'f1': round(float(f1_score(y_test, y_pred, zero_division=0)), 6),
            'roc_auc': round(float(roc_auc_score(y_test, y_score)), 6),
        },
        'confusion_matrix': {
            'labels': ['Not <30', '<30'],
            'matrix': confusion_matrix(y_test, y_pred).tolist(),
        },
    }

    if hasattr(clf, 'coef_'):
        coefs = pd.Series(clf.coef_[0], index=feature_names)
        result['top_positive_features'] = [
            {'feature': k, 'coefficient': round(float(v), 6)}
            for k, v in coefs.sort_values(ascending=False).head(12).items()
        ]
        result['top_negative_features'] = [
            {'feature': k, 'coefficient': round(float(v), 6)}
            for k, v in coefs.sort_values(ascending=True).head(12).items()
        ]
    elif hasattr(clf, 'feature_importances_'):
        importances = pd.Series(clf.feature_importances_, index=feature_names)
        result['top_features'] = [
            {'feature': k, 'importance': round(float(v), 6)}
            for k, v in importances.sort_values(ascending=False).head(15).items()
        ]

    return result


def run_baseline_model(model_ready_df, verbose=True):
    """Train several baseline models for the UI test page."""
    X = model_ready_df.drop(columns=['readmitted'])
    y = model_ready_df['readmitted'].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    pos_count = int(y_train.sum())
    neg_count = int(len(y_train) - pos_count)
    scale_pos_weight = neg_count / pos_count if pos_count else 1.0

    model_specs = [
        (
            'Logistic Regression',
            LogisticRegression(max_iter=1000, class_weight='balanced', solver='liblinear'),
            'standardized numeric + one-hot categorical',
        ),
        (
            'Random Forest',
            RandomForestClassifier(
                n_estimators=160,
                max_depth=12,
                min_samples_leaf=25,
                class_weight='balanced_subsample',
                random_state=42,
                n_jobs=-1,
            ),
            'standardized numeric + one-hot categorical',
        ),
    ]

    if XGBClassifier is not None:
        model_specs.append((
            'XGBoost',
            XGBClassifier(
                n_estimators=260,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.85,
                colsample_bytree=0.85,
                objective='binary:logistic',
                eval_metric='logloss',
                scale_pos_weight=scale_pos_weight,
                random_state=42,
                n_jobs=-1,
                tree_method='hist',
            ),
            'standardized numeric + one-hot categorical',
        ))

    model_results = [
        _evaluate_classifier(name, clf, X_train, X_test, y_train, y_test, X.columns, feature_mode)
        for name, clf, feature_mode in model_specs
    ]
    best_model = max(model_results, key=lambda r: r['metrics']['roc_auc'])
    logistic_result = next(r for r in model_results if r['model_name'] == 'Logistic Regression')

    report = {
        'model_name': best_model['model_name'],
        'purpose': 'Baseline comparison across simple ML models on the same model-ready dataset. These are first-pass sanity checks before deeper tuning.',
        'split': {'train_rows': int(len(X_train)), 'test_rows': int(len(X_test)), 'test_size': 0.2, 'random_state': 42},
        'class_balance': {
            'train_positive_rate': round(float(y_train.mean()), 6),
            'test_positive_rate': round(float(y_test.mean()), 6),
            'scale_pos_weight_for_xgboost': round(float(scale_pos_weight), 6),
        },
        'models': model_results,
        'best_model': best_model,
        'metrics': best_model['metrics'],
        'confusion_matrix': best_model['confusion_matrix'],
        'top_positive_features': logistic_result.get('top_positive_features', []),
        'top_negative_features': logistic_result.get('top_negative_features', []),
        'notes': [
            'Random Forest uses class_weight=balanced_subsample to reduce majority-class dominance.',
            'XGBoost uses scale_pos_weight = negative_train_count / positive_train_count when xgboost is installed.',
            'All models are evaluated on the same stratified 80/20 split.',
        ],
    }

    if verbose:
        print("  Baseline model comparison:")
        for result in model_results:
            metrics = result['metrics']
            print(f"    {result['model_name']}: AUC={metrics['roc_auc']} F1={metrics['f1']} Recall={metrics['recall']}")

    return report


if __name__ == "__main__":
    BASE = Path('/home/sina/Downloads/data/CSE4062S26_Grp2')
    INPUT  = BASE / 'data/diabetes+130-us+hospitals+for+years+1999-2008/diabetic_data.csv'
    OUTPUT = BASE / 'data/cleaned_diabetic_data.csv'
    MODEL_READY_OUTPUT = BASE / 'data/model_ready_diabetic_data.csv'
    MODEL_READY_JSON = BASE / 'user_tools/visualisation_tool/model_ready_data.json'
    BASELINE_JSON = BASE / 'user_tools/visualisation_tool/baseline_model_report.json'

    cleaned_df, nzv_report = load_and_clean_data(INPUT)
    cleaned_df.to_csv(OUTPUT, index=False)
    print(f"\nCleaned data saved to {OUTPUT}")

    model_ready_df, model_ready_report = make_model_ready_data(cleaned_df, nzv_report)
    model_ready_df.to_csv(MODEL_READY_OUTPUT, index=False)
    print(f"Model-ready data saved to {MODEL_READY_OUTPUT}")

    with open(MODEL_READY_JSON, 'w') as f:
        json.dump(model_ready_report, f, indent=2)
    print(f"Model-ready report saved to {MODEL_READY_JSON}")

    baseline_report = run_baseline_model(model_ready_df)
    with open(BASELINE_JSON, 'w') as f:
        json.dump(baseline_report, f, indent=2)
    print(f"Baseline model report saved to {BASELINE_JSON}")

    # Save NZV report as JSON for the frontend
    NZV_JSON = BASE / 'user_tools/visualisation_tool/nzv_report.json'
    # Convert numpy bools/floats to native Python types for JSON
    nzv_report_serializable = {
        col: {k: (bool(v) if isinstance(v, (bool, np.bool_)) else
                  float(v) if isinstance(v, (float, np.floating)) else v)
              for k, v in metrics.items()}
        for col, metrics in nzv_report.items()
    }
    with open(NZV_JSON, 'w') as f:
        json.dump(nzv_report_serializable, f, indent=2)
    print(f"NZV report saved to {NZV_JSON}")
