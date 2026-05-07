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
from itertools import combinations
from collections import Counter

from sklearn.compose import ColumnTransformer
from sklearn.cluster import AgglomerativeClustering, DBSCAN, KMeans
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.feature_selection import RFE, SelectKBest, chi2, mutual_info_classif
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.metrics import silhouette_score
from sklearn.model_selection import ParameterGrid
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
    r2_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.preprocessing import MinMaxScaler

from scipy.stats import binomtest

try:
    from xgboost import XGBClassifier
except ImportError:
    XGBClassifier = None

try:
    from xgboost import XGBRegressor
except ImportError:
    XGBRegressor = None

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


def to_jsonable(value):
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        if np.isnan(value) or np.isinf(value):
            return None
        return value
    if isinstance(value, np.ndarray):
        return [to_jsonable(v) for v in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    return value


def build_roc_payload(y_true, y_score):
    fpr, tpr, thresholds = roc_curve(y_true, y_score)
    return {
        'fpr': [round(float(v), 6) for v in fpr],
        'tpr': [round(float(v), 6) for v in tpr],
        'thresholds': [round(float(v), 6) for v in thresholds],
    }


def mcnemar_exact(best_pred, competitor_pred, y_true):
    best_pred = np.asarray(best_pred)
    competitor_pred = np.asarray(competitor_pred)
    y_true = np.asarray(y_true)
    best_correct = best_pred == y_true
    comp_correct = competitor_pred == y_true
    b = int(np.sum(best_correct & ~comp_correct))
    c = int(np.sum(~best_correct & comp_correct))
    n = b + c
    p_value = float(binomtest(min(b, c), n=n, p=0.5, alternative='two-sided').pvalue) if n else 1.0
    return {
        'best_only_correct': b,
        'competitor_only_correct': c,
        'discordant_pairs': n,
        'exact_p_value': round(p_value, 6),
        'significant_at_0.05': p_value < 0.05,
    }


def apriori_from_transactions(transactions, min_support=0.08, min_confidence=0.6, max_length=3):
    total = len(transactions)
    if total == 0:
        return {'min_support': min_support, 'min_confidence': min_confidence, 'frequent_itemsets': [], 'rules': []}

    item_counts = Counter()
    for items in transactions:
        item_counts.update(set(items))

    frequent = {}
    for item, count in item_counts.items():
        support = count / total
        if support >= min_support:
            frequent[frozenset([item])] = count

    all_frequent = dict(frequent)
    k = 2
    current_level = list(frequent.keys())
    while current_level and k <= max_length:
        candidates = set()
        for a, b in combinations(current_level, 2):
            union = a | b
            if len(union) == k:
                candidates.add(union)
        next_level = {}
        for candidate in candidates:
            count = sum(1 for items in transactions if candidate.issubset(items))
            if count / total >= min_support:
                next_level[candidate] = count
        all_frequent.update(next_level)
        current_level = list(next_level.keys())
        k += 1

    frequent_itemsets = [
        {
            'items': sorted(list(itemset)),
            'support': round(count / total, 6),
            'count': int(count),
        }
        for itemset, count in sorted(all_frequent.items(), key=lambda x: (-len(x[0]), -(x[1] / total), sorted(x[0])))
    ]

    rules = []
    for itemset, count in all_frequent.items():
        if len(itemset) < 2:
            continue
        itemset_support = count / total
        items = list(itemset)
        for r in range(1, len(items)):
            for antecedent in combinations(items, r):
                antecedent = frozenset(antecedent)
                consequent = itemset - antecedent
                antecedent_count = all_frequent.get(antecedent)
                consequent_count = all_frequent.get(consequent)
                if not antecedent_count or not consequent_count:
                    continue
                confidence = count / antecedent_count
                if confidence < min_confidence:
                    continue
                support_consequent = consequent_count / total
                lift = confidence / support_consequent if support_consequent else None
                rules.append({
                    'antecedent': sorted(list(antecedent)),
                    'consequent': sorted(list(consequent)),
                    'support': round(itemset_support, 6),
                    'confidence': round(float(confidence), 6),
                    'lift': round(float(lift), 6) if lift is not None else None,
                    'count': int(count),
                })

    rules = sorted(rules, key=lambda r: (-r['lift'], -r['confidence'], -r['support']))[:25]
    return {
        'min_support': min_support,
        'min_confidence': min_confidence,
        'max_length': max_length,
        'total_transactions': total,
        'frequent_itemsets': frequent_itemsets[:50],
        'rules': rules,
    }


def _normalized_feature_rank_scores(series):
    ordered = series.sort_values(ascending=False)
    total = max(len(ordered), 1)
    scores = {}
    for idx, (feature, _) in enumerate(ordered.items(), start=1):
        scores[feature] = (total - idx + 1) / total
    return pd.Series(scores).sort_values(ascending=False)


def _build_consensus_ranking(rankings):
    if not rankings:
        return pd.Series(dtype=float)

    union = sorted({feature for series in rankings.values() for feature in series.index})
    consensus = pd.DataFrame(index=union)
    for name, series in rankings.items():
        ranks = series.rank(ascending=False, method='average')
        consensus[name] = ranks
    consensus['mean_rank'] = consensus.mean(axis=1)
    consensus['consensus_score'] = 1 / consensus['mean_rank']
    return consensus['consensus_score'].sort_values(ascending=False)


def generate_feature_selection_report(model_ready_df, verbose=True):
    X = model_ready_df.drop(columns=['readmitted'])
    y = model_ready_df['readmitted'].astype(int)
    X_train, _, y_train, _ = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    train_sample_X, train_sample_y = stratified_sample(X_train, y_train, n_samples=12000, random_state=42)
    train_sample_X = train_sample_X.copy()
    train_sample_y = train_sample_y.copy()

    mi_selector = SelectKBest(score_func=mutual_info_classif, k='all')
    mi_selector.fit(train_sample_X, train_sample_y)
    mi_scores = pd.Series(mi_selector.scores_, index=train_sample_X.columns).fillna(0.0).sort_values(ascending=False)

    scaled_X = MinMaxScaler().fit_transform(train_sample_X)
    chi_selector = SelectKBest(score_func=chi2, k='all')
    chi_selector.fit(scaled_X, train_sample_y)
    chi_scores = pd.Series(chi_selector.scores_, index=train_sample_X.columns).fillna(0.0).sort_values(ascending=False)

    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=20,
        class_weight='balanced_subsample',
        random_state=42,
        n_jobs=-1,
    )
    rf.fit(train_sample_X, train_sample_y)
    rf_scores = pd.Series(rf.feature_importances_, index=train_sample_X.columns).sort_values(ascending=False)

    lr = LogisticRegression(max_iter=1000, class_weight='balanced', solver='liblinear')
    lr.fit(train_sample_X, train_sample_y)
    lr_scores = pd.Series(np.abs(lr.coef_[0]), index=train_sample_X.columns).sort_values(ascending=False)

    rfe_base = LogisticRegression(max_iter=1000, class_weight='balanced', solver='liblinear')
    rfe = RFE(
        estimator=rfe_base,
        n_features_to_select=min(20, max(12, train_sample_X.shape[1] // 4)),
        step=0.1,
    )
    rfe.fit(train_sample_X, train_sample_y)
    rfe_scores = pd.Series(1.0 / np.maximum(rfe.ranking_, 1), index=train_sample_X.columns).sort_values(ascending=False)

    methods = {
        'mutual_information': mi_scores,
        'chi_square': chi_scores,
        'random_forest_importance': rf_scores,
        'logistic_abs_coefficient': lr_scores,
        'rfe_logistic': rfe_scores,
    }
    consensus_scores = _build_consensus_ranking(methods)
    methods['consensus_rank'] = consensus_scores

    report = {
        'split': {
            'train_rows': int(len(X_train)),
            'analysis_rows': int(len(train_sample_X)),
            'test_rows': int(len(X) - len(X_train)),
            'random_state': 42,
        },
        'methods': {
            name: {
                'top_features': [
                    {'feature': feat, 'score': round(float(score), 6)}
                    for feat, score in series.head(20).items()
                ],
            }
            for name, series in methods.items()
        },
        'selected_feature_sets': {
            'mutual_information_top20': mi_scores.head(20).index.tolist(),
            'chi_square_top20': chi_scores.head(20).index.tolist(),
            'random_forest_top20': rf_scores.head(20).index.tolist(),
            'logistic_top20': lr_scores.head(20).index.tolist(),
            'rfe_top20': rfe_scores.head(20).index.tolist(),
            'consensus_top20': consensus_scores.head(20).index.tolist(),
        },
        'notes': [
            'Feature rankings are estimated on a stratified training sample to reduce leakage.',
            'RFE uses logistic regression as the recursive selector and consensus ranking aggregates all available methods.',
        ],
    }

    if verbose:
        print("  Feature selection report prepared:")
        for name, payload in report['methods'].items():
            print(f"    {name}: {payload['top_features'][0]['feature']} ({payload['top_features'][0]['score']})")

    return report


def generate_feature_subset_experiments(model_ready_df, feature_sets, verbose=True):
    X = model_ready_df.drop(columns=['readmitted'])
    y = model_ready_df['readmitted'].astype(int)
    X_train_full, X_test_full, y_train_full, y_test_full = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    experiments = []
    for set_name, cols in feature_sets.items():
        cols = [c for c in cols if c in X.columns]
        if not cols:
            continue
        X_train = X_train_full[cols]
        X_test = X_test_full[cols]
        candidates = [
            (
                'Logistic Regression',
                LogisticRegression(max_iter=1000, class_weight='balanced', solver='liblinear'),
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
            ),
        ]
        for model_name, clf in candidates:
            result = _evaluate_classifier(model_name, clf, X_train, X_test, y_train_full, y_test_full, cols, f'{set_name} subset')
            result['feature_set_name'] = set_name
            result['feature_count'] = len(cols)
            experiments.append(result)

    experiments = sorted(experiments, key=lambda r: (r['feature_set_name'], r['model_name']))
    if verbose:
        print(f"  Feature subset experiments prepared: {len(experiments)} runs")
    return {
        'feature_sets': {name: cols for name, cols in feature_sets.items()},
        'experiments': experiments,
    }


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
        'predictions': [int(v) for v in y_pred.tolist()],
        'roc_curve': build_roc_payload(y_test, y_score),
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
        (
            'Gradient Boosting',
            GradientBoostingClassifier(
                n_estimators=150,
                learning_rate=0.08,
                max_depth=3,
                random_state=42,
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
    closest_competitor = sorted(
        [r for r in model_results if r['model_name'] != best_model['model_name']],
        key=lambda r: abs(r['metrics']['roc_auc'] - best_model['metrics']['roc_auc'])
    )[0]

    significance = mcnemar_exact(
        best_model['predictions'],
        closest_competitor['predictions'],
        y_test,
    )

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
        'closest_competitor': closest_competitor,
        'significance_analysis': significance,
        'metrics': best_model['metrics'],
        'confusion_matrix': best_model['confusion_matrix'],
        'top_positive_features': logistic_result.get('top_positive_features', []),
        'top_negative_features': logistic_result.get('top_negative_features', []),
        'roc_curves': {
            result['model_name']: result['roc_curve']
            for result in model_results
        },
        'notes': [
            'Random Forest uses class_weight=balanced_subsample to reduce majority-class dominance.',
            'XGBoost uses scale_pos_weight = negative_train_count / positive_train_count when xgboost is installed.',
            'Gradient Boosting provides a non-linear baseline without external dependencies.',
            'All models are evaluated on the same stratified 80/20 split.',
        ],
    }

    if verbose:
        print("  Baseline model comparison:")
        for result in model_results:
            metrics = result['metrics']
            print(f"    {result['model_name']}: AUC={metrics['roc_auc']} F1={metrics['f1']} Recall={metrics['recall']}")

    return report


def stratified_sample(X, y, n_samples, random_state=42):
    if len(X) <= n_samples:
        return X, y
    _, X_sample, _, y_sample = train_test_split(
        X, y,
        test_size=n_samples,
        random_state=random_state,
        stratify=y,
    )
    return X_sample, y_sample


def random_sample(X, y, n_samples, random_state=42):
    if len(X) <= n_samples:
        return X, y
    rng = np.random.default_rng(random_state)
    indices = rng.choice(np.arange(len(X)), size=n_samples, replace=False)
    return X.iloc[indices], y.iloc[indices]


def build_model_lab_specs(scale_pos_weight):
    """Return the interactive model-lab search space and control metadata."""
    specs = {
        'k-NN': {
            'params': {'n_neighbors': [7, 21, 41], 'weights': ['uniform', 'distance']},
            'factory': lambda p: KNeighborsClassifier(**p),
            'controls': [
                {'name': 'n_neighbors', 'label': 'Neighbors', 'type': 'select', 'values': [7, 21, 41]},
                {'name': 'weights', 'label': 'Weighting', 'type': 'select', 'values': ['uniform', 'distance']},
            ],
        },
        'Naive Bayes': {
            'params': {'var_smoothing': [1e-9, 1e-8, 1e-7]},
            'factory': lambda p: GaussianNB(**p),
            'controls': [
                {'name': 'var_smoothing', 'label': 'Variance smoothing', 'type': 'select', 'values': [1e-9, 1e-8, 1e-7]},
            ],
        },
        'Decision Tree': {
            'params': {'max_depth': [4, 8, 12], 'min_samples_leaf': [20, 60]},
            'factory': lambda p: DecisionTreeClassifier(**p, class_weight='balanced', random_state=42),
            'controls': [
                {'name': 'max_depth', 'label': 'Max depth', 'type': 'select', 'values': [4, 8, 12]},
                {'name': 'min_samples_leaf', 'label': 'Min samples leaf', 'type': 'select', 'values': [20, 60]},
            ],
        },
        'Random Forest': {
            'params': {'n_estimators': [100, 180], 'max_depth': [10, 14], 'min_samples_leaf': [20]},
            'factory': lambda p: RandomForestClassifier(**p, class_weight='balanced_subsample', random_state=42, n_jobs=-1),
            'controls': [
                {'name': 'n_estimators', 'label': 'Trees', 'type': 'select', 'values': [100, 180]},
                {'name': 'max_depth', 'label': 'Max depth', 'type': 'select', 'values': [10, 14]},
                {'name': 'min_samples_leaf', 'label': 'Min samples leaf', 'type': 'select', 'values': [20]},
            ],
        },
        'MLP': {
            'params': {'hidden_layer_sizes': [(32,), (64,), (64, 32)], 'alpha': [0.0001, 0.001]},
            'factory': lambda p: MLPClassifier(**p, max_iter=120, early_stopping=True, random_state=42),
            'controls': [
                {'name': 'hidden_layer_sizes', 'label': 'Hidden layers', 'type': 'select', 'values': ['32', '64', '64,32']},
                {'name': 'alpha', 'label': 'L2 alpha', 'type': 'select', 'values': [0.0001, 0.001]},
            ],
            'display_params': lambda p: {**p, 'hidden_layer_sizes': ','.join(map(str, p['hidden_layer_sizes']))},
        },
        'SVM (RBF)': {
            'params': {'C': [0.5, 1.0, 2.0], 'gamma': ['scale', 0.01]},
            'factory': lambda p: SVC(**p, kernel='rbf', class_weight='balanced', probability=True, random_state=42),
            'controls': [
                {'name': 'C', 'label': 'C', 'type': 'select', 'values': [0.5, 1.0, 2.0]},
                {'name': 'gamma', 'label': 'Gamma', 'type': 'select', 'values': ['scale', 0.01]},
            ],
        },
    }

    if XGBClassifier is not None:
        specs['XGBoost'] = {
            'params': {'n_estimators': [180, 280], 'max_depth': [3, 4], 'learning_rate': [0.05, 0.1]},
            'factory': lambda p: XGBClassifier(
                **p,
                objective='binary:logistic',
                eval_metric='logloss',
                scale_pos_weight=scale_pos_weight,
                subsample=0.85,
                colsample_bytree=0.85,
                random_state=42,
                n_jobs=-1,
                tree_method='hist',
            ),
            'controls': [
                {'name': 'n_estimators', 'label': 'Trees', 'type': 'select', 'values': [180, 280]},
                {'name': 'max_depth', 'label': 'Max depth', 'type': 'select', 'values': [3, 4]},
                {'name': 'learning_rate', 'label': 'Learning rate', 'type': 'select', 'values': [0.05, 0.1]},
            ],
        }
    else:
        specs['XGBoost'] = {
            'params': {},
            'factory': None,
            'controls': [],
            'unavailable_reason': 'xgboost package is not installed. Install requirements.txt to enable it.',
        }

    return specs


def normalize_lab_param_value(name, value):
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if value is None:
        return None

    if name == 'hidden_layer_sizes':
        if isinstance(value, (list, tuple)):
            return tuple(int(v) for v in value)
        parts = [part.strip() for part in str(value).split(',') if part.strip()]
        return tuple(int(part) for part in parts)

    if isinstance(value, str):
        text = value.strip()
        if text.lower() == 'true':
            return True
        if text.lower() == 'false':
            return False
        try:
            if any(ch in text for ch in ['.', 'e', 'E']):
                return float(text)
            return int(text)
        except ValueError:
            return text

    return value


def normalize_lab_params(algorithm_name, raw_params):
    parsed = {key: normalize_lab_param_value(key, value) for key, value in (raw_params or {}).items()}
    if algorithm_name == 'MLP' and 'hidden_layer_sizes' in parsed and not isinstance(parsed['hidden_layer_sizes'], tuple):
        parsed['hidden_layer_sizes'] = normalize_lab_param_value('hidden_layer_sizes', parsed['hidden_layer_sizes'])
    return parsed


def run_single_model_lab_experiment(model_ready_df, algorithm_name, raw_params, verbose=True):
    """Train a single live experiment for the selected model-lab configuration."""
    X = model_ready_df.drop(columns=['readmitted'])
    y = model_ready_df['readmitted'].astype(int)

    X_train_full, X_test_full, y_train_full, y_test_full = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    X_train, y_train = stratified_sample(X_train_full, y_train_full, n_samples=6000, random_state=42)
    X_test, y_test = stratified_sample(X_test_full, y_test_full, n_samples=2500, random_state=43)

    pos_count = int(y_train.sum())
    neg_count = int(len(y_train) - pos_count)
    scale_pos_weight = neg_count / pos_count if pos_count else 1.0
    specs = build_model_lab_specs(scale_pos_weight)

    spec = specs.get(algorithm_name)
    if not spec or spec.get('factory') is None:
        raise ValueError(spec.get('unavailable_reason') if spec else f'Unknown algorithm: {algorithm_name}')

    params = normalize_lab_params(algorithm_name, raw_params)
    clf = spec['factory'](params)
    result = _evaluate_classifier(
        algorithm_name, clf, X_train, X_test, y_train, y_test, X.columns,
        feature_mode='sampled model-ready encoded features',
    )
    result['params'] = spec.get('display_params', lambda p: p)(params)
    result['source'] = 'live'
    result['sample'] = {
        'train_rows': int(len(X_train)),
        'test_rows': int(len(X_test)),
        'positive_rate_train': round(float(y_train.mean()), 6),
        'positive_rate_test': round(float(y_test.mean()), 6),
        'full_train_rows': int(len(X_train_full)),
        'full_test_rows': int(len(X_test_full)),
    }
    if verbose:
        metrics = result['metrics']
        print(f"    Live {algorithm_name}: AUC={metrics['roc_auc']} F1={metrics['f1']} Recall={metrics['recall']}")
    return result


def run_model_lab(model_ready_df, verbose=True):
    """Generate precomputed hyperparameter runs for the interactive model lab."""
    X = model_ready_df.drop(columns=['readmitted'])
    y = model_ready_df['readmitted'].astype(int)

    X_train_full, X_test_full, y_train_full, y_test_full = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    X_train, y_train = stratified_sample(X_train_full, y_train_full, n_samples=6000, random_state=42)
    X_test, y_test = stratified_sample(X_test_full, y_test_full, n_samples=2500, random_state=43)

    pos_count = int(y_train.sum())
    neg_count = int(len(y_train) - pos_count)
    scale_pos_weight = neg_count / pos_count if pos_count else 1.0
    algorithm_specs = build_model_lab_specs(scale_pos_weight)

    algorithms = []
    for name in ['k-NN', 'Naive Bayes', 'Decision Tree', 'Random Forest', 'XGBoost', 'MLP', 'SVM (RBF)']:
        spec = algorithm_specs[name]
        runs = []
        if spec.get('factory') is not None:
            for raw_params in ParameterGrid(spec['params']):
                clf = spec['factory'](raw_params)
                result = _evaluate_classifier(
                    name, clf, X_train, X_test, y_train, y_test, X.columns,
                    feature_mode='sampled model-ready encoded features',
                )
                display_params = spec.get('display_params', lambda p: p)(raw_params)
                result['params'] = display_params
                runs.append(result)
        best = max(runs, key=lambda r: r['metrics']['roc_auc']) if runs else None
        algorithms.append({
            'name': name,
            'controls': spec['controls'],
            'runs': runs,
            'best': best,
            'unavailable_reason': spec.get('unavailable_reason'),
        })
        if verbose and best:
            metrics = best['metrics']
            print(f"    Lab {name}: best AUC={metrics['roc_auc']} F1={metrics['f1']}")

    all_runs = [run for alg in algorithms for run in alg['runs']]
    best_overall = max(all_runs, key=lambda r: r['metrics']['roc_auc']) if all_runs else None

    return {
        'title': 'Interactive Algorithm Test Lab',
        'sample_policy': 'Precomputed hyperparameter grid on a stratified sample for responsive dashboard tuning.',
        'sample': {
            'train_rows': int(len(X_train)),
            'test_rows': int(len(X_test)),
            'positive_rate_train': round(float(y_train.mean()), 6),
            'positive_rate_test': round(float(y_test.mean()), 6),
            'full_train_rows': int(len(X_train_full)),
            'full_test_rows': int(len(X_test_full)),
        },
        'algorithms': algorithms,
        'best_overall': best_overall,
    }


def generate_clustering_report(model_ready_df, cleaned_df, verbose=True):
    """Create PCA coordinates and clustering labels for the clustering page."""
    X = model_ready_df.drop(columns=['readmitted'])
    y = model_ready_df['readmitted'].astype(int)
    X_sample, y_sample = stratified_sample(X, y, n_samples=1800, random_state=101)
    meta = cleaned_df.loc[X_sample.index].copy()

    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(X_sample)

    def summarize_labels(labels, y_values):
        labels = np.asarray(labels)
        sizes = pd.Series(labels).value_counts().sort_index().to_dict()
        readmit_rates = {}
        for label in sorted(set(labels)):
            mask = labels == label
            readmit_rates[str(int(label))] = round(float(y_values.iloc[mask].mean()), 6) if mask.any() else 0.0
        if len(set(labels)) > 1:
            try:
                silhouette = round(float(silhouette_score(coords[labels != -1], labels[labels != -1])) if -1 in labels and np.sum(labels != -1) > len(set(labels[labels != -1])) else silhouette_score(coords, labels), 6)
            except Exception:
                silhouette = None
        else:
            silhouette = None
        return {
            'labels': [int(v) for v in labels],
            'sizes': {str(int(key)): int(val) for key, val in sizes.items()},
            'readmission_rates': readmit_rates,
            'silhouette': silhouette,
            'cluster_count': int(len([k for k in set(labels) if k != -1])),
            'noise_count': int(np.sum(labels == -1)),
        }

    kmeans_runs = {}
    hierarchical_runs = {}
    for k in range(2, 9):
        km = KMeans(n_clusters=k, n_init=10, random_state=42)
        kmeans_runs[str(k)] = summarize_labels(km.fit_predict(coords), y_sample)

        hc = AgglomerativeClustering(n_clusters=k, linkage='ward')
        hierarchical_runs[str(k)] = summarize_labels(hc.fit_predict(coords), y_sample)

    dbscan_runs = []
    for eps in [0.35, 0.45, 0.55, 0.65]:
        for min_samples in [10, 15, 20]:
            db = DBSCAN(eps=eps, min_samples=min_samples)
            labels = db.fit_predict(coords)
            clusters = len({int(v) for v in labels if v != -1})
            if clusters < 2:
                continue
            summary = summarize_labels(labels, y_sample)
            summary['eps'] = eps
            summary['min_samples'] = min_samples
            dbscan_runs.append(summary)

    best_dbscan = max(
        dbscan_runs,
        key=lambda r: (-1 if r.get('silhouette') is None else r['silhouette'], -r['cluster_count'], -r['noise_count'])
    ) if dbscan_runs else None

    best_kmeans = max(
        (v for v in kmeans_runs.values() if v.get('silhouette') is not None),
        key=lambda r: r['silhouette'],
        default=None,
    )
    best_hierarchical = max(
        (v for v in hierarchical_runs.values() if v.get('silhouette') is not None),
        key=lambda r: r['silhouette'],
        default=None,
    )

    points = []
    for pos, idx in enumerate(X_sample.index):
        row = meta.loc[idx]
        points.append({
            'x': round(float(coords[pos, 0]), 6),
            'y': round(float(coords[pos, 1]), 6),
            'readmitted': int(y_sample.loc[idx]),
            'race': str(row.get('race', 'Unknown')),
            'age': str(row.get('age', 'Unknown')),
            'diag_1_group': map_icd9(row.get('diag_1', 'Unknown')),
            'time_in_hospital': int(row.get('time_in_hospital', 0)),
        })

    if verbose:
        print(f"  Clustering sample: {len(points)} rows, PCA variance={pca.explained_variance_ratio_.sum():.4f}")

    return {
        'title': 'PCA + Clustering Comparison Lab',
        'method': {
            'projection': 'PCA(n_components=2) on the model-ready encoded feature matrix',
            'clustering': 'KMeans and hierarchical clustering evaluated for k=2..8; DBSCAN evaluated over several eps/min_samples configurations on the PCA coordinates',
            'sample_rows': len(points),
            'explained_variance_ratio': [round(float(v), 6) for v in pca.explained_variance_ratio_],
            'total_explained_variance': round(float(pca.explained_variance_ratio_.sum()), 6),
        },
        'points': points,
        'methods': {
            'kmeans': {
                'label': 'KMeans',
                'parameter_name': 'k',
                'parameter_values': [str(k) for k in range(2, 9)],
                'runs': kmeans_runs,
                'best': best_kmeans,
            },
            'hierarchical': {
                'label': 'Hierarchical',
                'parameter_name': 'k',
                'parameter_values': [str(k) for k in range(2, 9)],
                'runs': hierarchical_runs,
                'best': best_hierarchical,
            },
            'dbscan': {
                'label': 'DBSCAN',
                'parameter_name': 'eps/min_samples',
                'runs': dbscan_runs,
                'best': best_dbscan,
            },
        },
    }


def generate_association_rules_report(cleaned_df, verbose=True):
    """Mine simple Apriori-style rules from a human-readable transaction table."""
    sample = cleaned_df.copy()
    if len(sample) > 5000:
        sample = sample.sample(n=5000, random_state=42)

    def bucket_time(value):
        try:
            v = float(value)
        except Exception:
            return 'unknown'
        if v <= 3:
            return '1-3'
        if v <= 6:
            return '4-6'
        return '7+'

    def bucket_visits(value):
        try:
            v = float(value)
        except Exception:
            return 'unknown'
        if v <= 0:
            return '0'
        if v == 1:
            return '1'
        return '2+'

    selected_cols = [
        'age', 'race', 'gender', 'A1Cresult', 'max_glu_serum', 'change', 'diabetesMed',
        'diag_1', 'diag_2', 'diag_3', 'admission_type_id', 'admission_source_id',
        'discharge_disposition_id', 'time_in_hospital', 'number_inpatient', 'number_emergency'
    ]

    transactions = []
    for _, row in sample.iterrows():
        items = []
        for col in selected_cols:
            if col not in row or pd.isna(row[col]):
                continue
            value = row[col]
            if col == 'time_in_hospital':
                value = bucket_time(value)
            elif col in {'number_inpatient', 'number_emergency'}:
                value = bucket_visits(value)
            items.append(f'{col}={value}')
        transactions.append(items)

    rules = apriori_from_transactions(
        transactions,
        min_support=0.08,
        min_confidence=0.6,
        max_length=3,
    )

    rules['columns_used'] = selected_cols
    rules['sample_rows'] = len(sample)

    if verbose:
        print(f"  Apriori report prepared: {len(rules['rules'])} rules from {len(sample)} rows")

    return rules


def _evaluate_regressor(name, reg, X_train, X_test, y_train, y_test, feature_names, feature_mode):
    X_train_values = X_train.to_numpy()
    X_test_values = X_test.to_numpy()
    reg.fit(X_train_values, y_train)
    y_pred = reg.predict(X_test_values)
    residuals = y_test - y_pred

    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    result = {
        'model_name': name,
        'feature_mode': feature_mode,
        'metrics': {
            'mae': round(float(mean_absolute_error(y_test, y_pred)), 6),
            'rmse': round(rmse, 6),
            'r2': round(float(r2_score(y_test, y_pred)), 6),
            'mean_residual': round(float(np.mean(residuals)), 6),
            'std_residual': round(float(np.std(residuals)), 6),
        },
        'predictions': [round(float(v), 6) for v in y_pred.tolist()],
        'actuals': [round(float(v), 6) for v in y_test.tolist()],
        'residuals': [round(float(v), 6) for v in residuals.tolist()],
    }

    sample_size = min(len(y_test), 1500)
    if sample_size > 0:
        sample_idx = np.linspace(0, len(y_test) - 1, sample_size, dtype=int)
        result['prediction_sample'] = [
            {
                'actual': round(float(y_test.iloc[i]), 6),
                'predicted': round(float(y_pred[i]), 6),
                'residual': round(float(y_test.iloc[i] - y_pred[i]), 6),
            }
            for i in sample_idx
        ]
    else:
        result['prediction_sample'] = []

    if hasattr(reg, 'coef_'):
        coefs = pd.Series(np.ravel(reg.coef_), index=feature_names)
        result['top_positive_features'] = [
            {'feature': k, 'coefficient': round(float(v), 6)}
            for k, v in coefs.sort_values(ascending=False).head(12).items()
        ]
        result['top_negative_features'] = [
            {'feature': k, 'coefficient': round(float(v), 6)}
            for k, v in coefs.sort_values(ascending=True).head(12).items()
        ]
    elif hasattr(reg, 'feature_importances_'):
        importances = pd.Series(reg.feature_importances_, index=feature_names)
        result['top_features'] = [
            {'feature': k, 'importance': round(float(v), 6)}
            for k, v in importances.sort_values(ascending=False).head(15).items()
        ]

    return result


def run_regression_model(model_ready_df, cleaned_df, verbose=True):
    """Predict hospital stay length using the model-ready matrix without the target leakage column."""
    X = model_ready_df.drop(columns=['readmitted', 'time_in_hospital'], errors='ignore')
    y = cleaned_df.loc[model_ready_df.index, 'time_in_hospital'].astype(float)

    if len(X) > 25000:
        X, y = random_sample(X, y, n_samples=25000, random_state=42)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model_specs = [
        (
            'Linear Regression',
            LinearRegression(),
            'model-ready encoded features without readmission label or target leakage',
        ),
        (
            'Ridge Regression',
            Ridge(alpha=1.0, random_state=42),
            'model-ready encoded features without readmission label or target leakage',
        ),
        (
            'Random Forest Regressor',
            RandomForestRegressor(
                n_estimators=160,
                max_depth=14,
                min_samples_leaf=20,
                random_state=42,
                n_jobs=-1,
            ),
            'model-ready encoded features without readmission label or target leakage',
        ),
        (
            'Gradient Boosting Regressor',
            GradientBoostingRegressor(
                n_estimators=150,
                learning_rate=0.08,
                max_depth=3,
                random_state=42,
            ),
            'model-ready encoded features without readmission label or target leakage',
        ),
    ]

    if XGBRegressor is not None:
        model_specs.append((
            'XGBoost Regressor',
            XGBRegressor(
                n_estimators=220,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.85,
                colsample_bytree=0.85,
                objective='reg:squarederror',
                random_state=42,
                n_jobs=-1,
                tree_method='hist',
            ),
            'model-ready encoded features without readmission label or target leakage',
        ))

    model_results = [
        _evaluate_regressor(name, reg, X_train, X_test, y_train, y_test, X.columns, feature_mode)
        for name, reg, feature_mode in model_specs
    ]
    best_model = min(model_results, key=lambda r: (r['metrics']['rmse'], -r['metrics']['r2']))
    closest_competitor = sorted(
        [r for r in model_results if r['model_name'] != best_model['model_name']],
        key=lambda r: abs(r['metrics']['rmse'] - best_model['metrics']['rmse'])
    )[0]

    y_pred_best = np.array(best_model['predictions'])
    y_test_best = np.array(best_model['actuals'])
    residuals = y_test_best - y_pred_best
    abs_residuals = np.abs(residuals)
    summary = {
        'mean_absolute_error': round(float(np.mean(abs_residuals)), 6),
        'median_absolute_error': round(float(np.median(abs_residuals)), 6),
        'p90_absolute_error': round(float(np.quantile(abs_residuals, 0.9)), 6),
        'max_absolute_error': round(float(np.max(abs_residuals)), 6),
    }

    report = {
        'target': 'time_in_hospital',
        'purpose': 'Regression benchmark for hospital stay length, inspired by the strongest operational forecasting branch reports.',
        'split': {
            'train_rows': int(len(X_train)),
            'test_rows': int(len(X_test)),
            'random_state': 42,
            'sampling_cap': 25000 if len(model_ready_df) > 25000 else len(model_ready_df),
        },
        'models': model_results,
        'best_model': best_model,
        'closest_competitor': closest_competitor,
        'metrics': best_model['metrics'],
        'comparison_table': [
            {
                'model_name': row['model_name'],
                'mae': row['metrics']['mae'],
                'rmse': row['metrics']['rmse'],
                'r2': row['metrics']['r2'],
            }
            for row in sorted(model_results, key=lambda r: (r['metrics']['rmse'], -r['metrics']['r2']))
        ],
        'residual_summary': summary,
        'prediction_sample': best_model.get('prediction_sample', []),
        'feature_signal': {
            'positive': best_model.get('top_positive_features', []),
            'negative': best_model.get('top_negative_features', []),
            'importance': best_model.get('top_features', []),
        },
        'notes': [
            'The target is the raw time_in_hospital value in days, not the scaled model-ready column.',
            'Rows are sampled only when necessary to keep the regression benchmark responsive.',
        ],
    }

    if verbose:
        print("  Regression model comparison:")
        for result in model_results:
            metrics = result['metrics']
            print(f"    {result['model_name']}: RMSE={metrics['rmse']} MAE={metrics['mae']} R2={metrics['r2']}")

    return report


if __name__ == "__main__":
    BASE = Path('/home/sina/Downloads/data/CSE4062S26_Grp2')
    INPUT  = BASE / 'data/diabetes+130-us+hospitals+for+years+1999-2008/diabetic_data.csv'
    OUTPUT = BASE / 'data/cleaned_diabetic_data.csv'
    MODEL_READY_OUTPUT = BASE / 'data/model_ready_diabetic_data.csv'
    MODEL_READY_JSON = BASE / 'user_tools/visualisation_tool/model_ready_data.json'
    BASELINE_JSON = BASE / 'user_tools/visualisation_tool/baseline_model_report.json'
    MODEL_LAB_JSON = BASE / 'user_tools/visualisation_tool/model_lab_report.json'
    REGRESSION_JSON = BASE / 'user_tools/visualisation_tool/regression_report.json'
    CLUSTERING_JSON = BASE / 'user_tools/visualisation_tool/clustering_report.json'
    FEATURE_SELECTION_JSON = BASE / 'user_tools/visualisation_tool/feature_selection_report.json'
    FEATURE_SUBSETS_JSON = BASE / 'user_tools/visualisation_tool/feature_subset_report.json'
    APRIORI_JSON = BASE / 'user_tools/visualisation_tool/association_rules_report.json'

    cleaned_df, nzv_report = load_and_clean_data(INPUT)
    cleaned_df.to_csv(OUTPUT, index=False)
    print(f"\nCleaned data saved to {OUTPUT}")

    model_ready_df, model_ready_report = make_model_ready_data(cleaned_df, nzv_report)
    model_ready_df.to_csv(MODEL_READY_OUTPUT, index=False)
    print(f"Model-ready data saved to {MODEL_READY_OUTPUT}")

    with open(MODEL_READY_JSON, 'w') as f:
        json.dump(model_ready_report, f, indent=2)
    print(f"Model-ready report saved to {MODEL_READY_JSON}")

    feature_selection_report = generate_feature_selection_report(model_ready_df)
    with open(FEATURE_SELECTION_JSON, 'w') as f:
        json.dump(to_jsonable(feature_selection_report), f, indent=2)
    print(f"Feature selection report saved to {FEATURE_SELECTION_JSON}")

    feature_subset_report = generate_feature_subset_experiments(
        model_ready_df,
        feature_selection_report['selected_feature_sets'],
    )
    with open(FEATURE_SUBSETS_JSON, 'w') as f:
        json.dump(to_jsonable(feature_subset_report), f, indent=2)
    print(f"Feature subset report saved to {FEATURE_SUBSETS_JSON}")

    baseline_report = run_baseline_model(model_ready_df)
    with open(BASELINE_JSON, 'w') as f:
        json.dump(to_jsonable(baseline_report), f, indent=2)
    print(f"Baseline model report saved to {BASELINE_JSON}")

    model_lab_report = run_model_lab(model_ready_df)
    with open(MODEL_LAB_JSON, 'w') as f:
        json.dump(to_jsonable(model_lab_report), f, indent=2)
    print(f"Interactive model lab report saved to {MODEL_LAB_JSON}")

    regression_report = run_regression_model(model_ready_df, cleaned_df)
    with open(REGRESSION_JSON, 'w') as f:
        json.dump(to_jsonable(regression_report), f, indent=2)
    print(f"Regression report saved to {REGRESSION_JSON}")

    clustering_report = generate_clustering_report(model_ready_df, cleaned_df)
    with open(CLUSTERING_JSON, 'w') as f:
        json.dump(to_jsonable(clustering_report), f, indent=2)
    print(f"Clustering report saved to {CLUSTERING_JSON}")

    apriori_report = generate_association_rules_report(cleaned_df)
    with open(APRIORI_JSON, 'w') as f:
        json.dump(to_jsonable(apriori_report), f, indent=2)
    print(f"Association rules report saved to {APRIORI_JSON}")

    # Save NZV report as JSON for the frontend
    NZV_JSON = BASE / 'user_tools/visualisation_tool/nzv_report.json'
    # Convert numpy bools/floats to native Python types for JSON
    nzv_report_serializable = to_jsonable(nzv_report)
    with open(NZV_JSON, 'w') as f:
        json.dump(nzv_report_serializable, f, indent=2)
    print(f"NZV report saved to {NZV_JSON}")
