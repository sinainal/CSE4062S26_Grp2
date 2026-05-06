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


def load_and_clean_data(file_path, verbose=True):
    """
    Full cleaning pipeline following Strack et al. (2014) and Kuhn & Johnson (2013).
    Returns (cleaned_df, nzv_report_dict)
    """
    if verbose:
        print("Loading data...")
    df = pd.read_csv(file_path, na_values=['?'], low_memory=False)
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


if __name__ == "__main__":
    INPUT  = '/home/sina/Downloads/data/CSE4062S26_Grp2/data/diabetes+130-us+hospitals+for+years+1999-2008/diabetic_data.csv'
    OUTPUT = '/home/sina/Downloads/data/CSE4062S26_Grp2/data/cleaned_diabetic_data.csv'

    cleaned_df, nzv_report = load_and_clean_data(INPUT)
    cleaned_df.to_csv(OUTPUT, index=False)
    print(f"\nCleaned data saved to {OUTPUT}")

    # Save NZV report as JSON for the frontend
    NZV_JSON = '/home/sina/Downloads/data/CSE4062S26_Grp2/user_tools/visualisation_tool/nzv_report.json'
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
