import pandas as pd
import json
import os
import numpy as np

# Comprehensive Dictionary for Diabetes 130-US Hospitals Dataset
FEATURE_DESCRIPTIONS = {
    "encounter_id": "Unique identifier of an encounter.",
    "patient_nbr": "Unique identifier of a patient.",
    "race": "Values: Caucasian, Asian, African American, Hispanic, and other.",
    "gender": "Values: male, female, and unknown/invalid.",
    "age": "Grouped in 10-year intervals: [0, 10), [10, 20), ..., [90, 100).",
    "weight": "Weight in pounds.",
    "admission_type_id": "Integer identifier corresponding to 9 distinct values, for example, emergency, urgent, elective, newborn, and not available.",
    "discharge_disposition_id": "Integer identifier corresponding to 29 distinct values, for example, discharged to home, expired, and not available.",
    "admission_source_id": "Integer identifier corresponding to 21 distinct values, for example, physician referral, emergency room, and transfer from a hospital.",
    "time_in_hospital": "Integer number of days between admission and discharge.",
    "payer_code": "Integer identifier corresponding to 23 distinct values, for example, Blue Cross/Blue Shield, Medicare, and self-pay.",
    "medical_specialty": "Integer identifier of a specialty of the admitting physician, corresponding to 84 distinct values.",
    "num_lab_procedures": "Number of lab tests performed during the encounter.",
    "num_procedures": "Number of procedures (other than lab tests) performed during the encounter.",
    "num_medications": "Number of distinct generic names administered during the encounter.",
    "number_outpatient": "Number of outpatient visits of the patient in the year preceding the encounter.",
    "number_emergency": "Number of emergency visits of the patient in the year preceding the encounter.",
    "number_inpatient": "Number of inpatient visits of the patient in the year preceding the encounter.",
    "diag_1": "The primary diagnosis (coded as first three digits of ICD9).",
    "diag_2": "Secondary diagnosis (coded as first three digits of ICD9).",
    "diag_3": "Additional secondary diagnosis (coded as first three digits of ICD9).",
    "number_diagnoses": "Number of diagnoses entered to the system.",
    "max_glu_serum": "Indicates the range of the result or if the test was not taken. Values: '>200', '>300', 'normal', and 'none'.",
    "A1Cresult": "Indicates the range of the result or if the test was not taken. Values: '>8', '>7', 'normal', and 'none'.",
    "change": "Indicates if there was a change in diabetic medications (either dosage or generic name). Values: 'change' and 'no change'.",
    "diabetesMed": "Indicates if there was any diabetic medication prescribed. Values: 'yes' and 'no'.",
    "readmitted": "Target Variable: Days to inpatient readmission. Values: '<30' if the patient was readmitted in less than 30 days, '>30' if the patient was readmitted in more than 30 days, and 'No' for no record of readmission."
}

# The 24 medication features have the same description pattern
medications = ['metformin', 'repaglinide', 'nateglinide', 'chlorpropamide', 'glimepiride', 'acetohexamide', 'glipizide', 'glyburide', 'tolbutamide', 'pioglitazone', 'rosiglitazone', 'acarbose', 'miglitol', 'troglitazone', 'tolazamide', 'examide', 'citoglipton', 'insulin', 'glyburide-metformin', 'glipizide-metformin', 'glimepiride-pioglitazone', 'metformin-rosiglitazone', 'metformin-pioglitazone']
for med in medications:
    FEATURE_DESCRIPTIONS[med] = f"Indicates whether the drug {med} was prescribed or there was a change in the dosage. Values: 'up', 'down', 'steady', and 'no'."

def generate_academic_report(csv_path, output_path):
    print("Loading data...")
    df = pd.read_csv(csv_path)
    
    df.replace('?', np.nan, inplace=True)
    
    report = {
        "dataset_overview": {},
        "raw_sample": [],
        "features": {}
    }
    
    report["dataset_overview"]["total_rows"] = len(df)
    report["dataset_overview"]["total_cols"] = len(df.columns)
    report["dataset_overview"]["total_missing_cells"] = int(df.isna().sum().sum())
    report["dataset_overview"]["duplicate_rows"] = int(df.duplicated().sum())
    
    sample_df = df.head(100).replace({np.nan: None})
    report["raw_sample"] = sample_df.to_dict(orient='records')
    
    for col in df.columns:
        col_data = df[col]
        is_numeric = pd.api.types.is_numeric_dtype(col_data)
        
        missing_count = int(col_data.isna().sum())
        missing_pct = round((missing_count / len(df)) * 100, 2)
        unique_count = int(col_data.nunique(dropna=True))
        
        feature_info = {
            "name": col,
            "description": FEATURE_DESCRIPTIONS.get(col, "No detailed description available for this feature."),
            "type": "Numeric" if is_numeric else "Categorical",
            "missing_count": missing_count,
            "missing_pct": missing_pct,
            "unique_count": unique_count,
            "stats": {},
            "distribution": {},
            "cleaning_method": "Keep",
            "cleaning_explanation": ""
        }
        
        # Determine Cleaning Method and Explanation
        if col in ['encounter_id', 'patient_nbr']:
            feature_info["cleaning_method"] = "Drop"
            feature_info["cleaning_explanation"] = "This is a unique identifier. Keeping it would cause data leakage or overfitting as it has no predictive clinical value."
        elif missing_pct > 40:
            feature_info["cleaning_method"] = "Drop"
            feature_info["cleaning_explanation"] = f"Feature has {missing_pct}% missing values. Imputation is statistically unreliable at this threshold. Safe to drop."
        elif unique_count == 1:
            feature_info["cleaning_method"] = "Drop"
            feature_info["cleaning_explanation"] = "Zero variance. Every row has the exact same value, offering zero discriminatory power for the model."
        elif col in ['diag_1', 'diag_2', 'diag_3']:
            feature_info["cleaning_method"] = "Group & Encode"
            feature_info["cleaning_explanation"] = "High cardinality ICD-9 codes. Recommended to group them into ~9 broader clinical categories (e.g., Circulatory, Respiratory) as per Strack et al. before encoding."
        elif is_numeric and missing_pct > 0:
            feature_info["cleaning_method"] = "Median Impute"
            feature_info["cleaning_explanation"] = "Numeric feature with missing values. Median imputation is robust to outliers compared to mean imputation."
        elif not is_numeric and missing_pct > 0:
            feature_info["cleaning_method"] = "Mode Impute / 'Missing' Category"
            feature_info["cleaning_explanation"] = "Categorical feature with missing values. Best to fill with the mode, or create a distinct 'Unknown' class if missingness itself is predictive."
        elif not is_numeric and unique_count > 10:
            feature_info["cleaning_method"] = "Target / Frequency Encode"
            feature_info["cleaning_explanation"] = "High cardinality categorical variable. One-hot encoding will explode dimensionality. Use Target Encoding or group rare categories."
        elif not is_numeric:
            feature_info["cleaning_method"] = "One-Hot Encode"
            feature_info["cleaning_explanation"] = "Low cardinality categorical variable. One-Hot Encoding is standard and prevents the model from assuming ordinality."
        else:
            feature_info["cleaning_method"] = "Scale / Standardize"
            feature_info["cleaning_explanation"] = "Standard numeric feature. Ready for modeling after applying StandardScaler or MinMaxScaler to ensure distance-based models perform well."

        if col == "readmitted":
            feature_info["cleaning_method"] = "Binarize (Target)"
            feature_info["cleaning_explanation"] = "This is the target variable. Depending on the goal, convert to binary (e.g., '<30' vs 'NO' or '>30') for binary classification."

        # Statistics
        if is_numeric:
            clean_data = col_data.dropna()
            feature_info["stats"]["mean"] = round(float(clean_data.mean()), 4) if not clean_data.empty else None
            feature_info["stats"]["std"] = round(float(clean_data.std()), 4) if not clean_data.empty else None
            feature_info["stats"]["min"] = float(clean_data.min()) if not clean_data.empty else None
            feature_info["stats"]["q25"] = float(clean_data.quantile(0.25)) if not clean_data.empty else None
            feature_info["stats"]["median"] = float(clean_data.median()) if not clean_data.empty else None
            feature_info["stats"]["q75"] = float(clean_data.quantile(0.75)) if not clean_data.empty else None
            feature_info["stats"]["max"] = float(clean_data.max()) if not clean_data.empty else None
            
            if not clean_data.empty:
                hist, bin_edges = np.histogram(clean_data, bins=20)
                feature_info["distribution"]["labels"] = [f"{bin_edges[i]:.1f}" for i in range(len(hist))]
                feature_info["distribution"]["values"] = hist.tolist()
        else:
            clean_data = col_data.dropna()
            top_counts = clean_data.value_counts().head(20)
            feature_info["distribution"]["labels"] = [str(idx) for idx in top_counts.index.tolist()]
            feature_info["distribution"]["values"] = top_counts.values.tolist()
            
        report["features"][col] = feature_info
        
    print("Writing JSON report...")
    with open(output_path, 'w') as f:
        json.dump(report, f)

if __name__ == "__main__":
    base_path = "/home/sina/Downloads/data/CSE4062S26_Grp2"
    csv_file = os.path.join(base_path, "data/diabetes+130-us+hospitals+for+years+1999-2008/diabetic_data.csv")
    output_json = os.path.join(base_path, "user_tools/visualisation_tool/academic_data.json")
    generate_academic_report(csv_file, output_json)
    print("Done.")
