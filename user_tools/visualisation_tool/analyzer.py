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
    "admission_type_id": "Mapped from IDS_mapping.csv (e.g., Emergency, Urgent, Elective).",
    "discharge_disposition_id": "Mapped from IDS_mapping.csv (e.g., Discharged to home, Expired).",
    "admission_source_id": "Mapped from IDS_mapping.csv (e.g., Physician Referral, Emergency Room).",
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

medications = ['metformin', 'repaglinide', 'nateglinide', 'chlorpropamide', 'glimepiride', 'acetohexamide', 'glipizide', 'glyburide', 'tolbutamide', 'pioglitazone', 'rosiglitazone', 'acarbose', 'miglitol', 'troglitazone', 'tolazamide', 'examide', 'citoglipton', 'insulin', 'glyburide-metformin', 'glipizide-metformin', 'glimepiride-pioglitazone', 'metformin-rosiglitazone', 'metformin-pioglitazone']
for med in medications:
    FEATURE_DESCRIPTIONS[med] = f"Indicates whether the drug {med} was prescribed or there was a change in the dosage. Values: 'up', 'down', 'steady', and 'no'."

def load_ids_mapping(mapping_path):
    mapping = {}
    if not os.path.exists(mapping_path): return mapping
    
    with open(mapping_path, 'r') as f:
        current_map = None
        for line in f:
            line = line.strip()
            if not line or line == ',': continue
            if 'admission_type_id' in line:
                current_map = 'admission_type_id'
                mapping[current_map] = {}
                continue
            if 'discharge_disposition_id' in line:
                current_map = 'discharge_disposition_id'
                mapping[current_map] = {}
                continue
            if 'admission_source_id' in line:
                current_map = 'admission_source_id'
                mapping[current_map] = {}
                continue
                
            if current_map:
                parts = line.split(',', 1)
                if len(parts) == 2:
                    try:
                        key = float(parts[0])
                        val = parts[1].strip('"').strip()
                        mapping[current_map][key] = val
                    except ValueError:
                        pass
    return mapping

def generate_academic_report(csv_path, mapping_path, output_path):
    print("Loading data...")
    df = pd.read_csv(csv_path)
    df.replace('?', np.nan, inplace=True)
    
    # Apply IDS Mapping
    mappings = load_ids_mapping(mapping_path)
    for col in mappings:
        if col in df.columns:
            # Map the float/int values to their string descriptions
            df[col] = df[col].astype(float).map(mappings[col]).fillna(df[col])
    
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
        
        # If numeric but very few unique values, treat its DISTRIBUTION like categorical (discrete)
        is_discrete = is_numeric and unique_count <= 30
        
        feature_info = {
            "name": col,
            "description": FEATURE_DESCRIPTIONS.get(col, "No detailed description available."),
            "type": "Numeric" if is_numeric else "Categorical",
            "missing_count": missing_count,
            "missing_pct": missing_pct,
            "unique_count": unique_count,
            "stats": {},
            "distribution": {},
            "cleaning_method": "Keep",
            "cleaning_explanation": ""
        }
        
        # Determine Cleaning Method
        if col in ['encounter_id', 'patient_nbr']:
            feature_info["cleaning_method"] = "Drop"
            feature_info["cleaning_explanation"] = "Unique identifier. Keeping it would cause data leakage or overfitting."
        elif missing_pct > 40:
            feature_info["cleaning_method"] = "Drop"
            feature_info["cleaning_explanation"] = f"Feature has {missing_pct}% missing values. Imputation is statistically unreliable at this threshold."
        elif unique_count == 1:
            feature_info["cleaning_method"] = "Drop"
            feature_info["cleaning_explanation"] = "Zero variance. Every row has the exact same value, offering zero predictive power."
        elif col in ['diag_1', 'diag_2', 'diag_3']:
            feature_info["cleaning_method"] = "Group & Encode"
            feature_info["cleaning_explanation"] = "High cardinality ICD-9 codes. Group into ~9 broader clinical categories (e.g., Circulatory, Respiratory)."
        elif is_numeric and missing_pct > 0:
            feature_info["cleaning_method"] = "Median Impute"
            feature_info["cleaning_explanation"] = "Numeric feature with missing values. Median imputation is robust to outliers."
        elif not is_numeric and missing_pct > 0:
            feature_info["cleaning_method"] = "Mode Impute / 'Missing' Category"
            feature_info["cleaning_explanation"] = "Categorical feature with missing values. Fill with mode or create a distinct 'Unknown' class."
        elif not is_numeric and unique_count > 10:
            feature_info["cleaning_method"] = "Target / Frequency Encode"
            feature_info["cleaning_explanation"] = "High cardinality categorical variable. One-hot encoding will explode dimensionality. Use Target Encoding."
        elif not is_numeric:
            feature_info["cleaning_method"] = "One-Hot Encode"
            feature_info["cleaning_explanation"] = "Low cardinality categorical variable. One-Hot Encoding is standard."
        else:
            feature_info["cleaning_method"] = "Scale / Standardize"
            feature_info["cleaning_explanation"] = "Standard numeric feature. Ready for modeling after scaling."

        if col == "readmitted":
            feature_info["cleaning_method"] = "Binarize (Target)"
            feature_info["cleaning_explanation"] = "Target variable. Convert to binary ('<30' vs 'NO' or '>30') for classification."

        # Statistics
        clean_data = col_data.dropna()
        if is_numeric:
            feature_info["stats"]["mean"] = round(float(clean_data.mean()), 4) if not clean_data.empty else None
            feature_info["stats"]["std"] = round(float(clean_data.std()), 4) if not clean_data.empty else None
            feature_info["stats"]["min"] = float(clean_data.min()) if not clean_data.empty else None
            feature_info["stats"]["q25"] = float(clean_data.quantile(0.25)) if not clean_data.empty else None
            feature_info["stats"]["median"] = float(clean_data.median()) if not clean_data.empty else None
            feature_info["stats"]["q75"] = float(clean_data.quantile(0.75)) if not clean_data.empty else None
            feature_info["stats"]["max"] = float(clean_data.max()) if not clean_data.empty else None
            
        if not clean_data.empty:
            if is_numeric and not is_discrete:
                # Continuous numeric -> standard histogram
                hist, bin_edges = np.histogram(clean_data, bins=20)
                feature_info["distribution"]["labels"] = [f"{bin_edges[i]:.1f}" for i in range(len(hist))]
                feature_info["distribution"]["values"] = hist.tolist()
            else:
                # Categorical OR Discrete Numeric -> exact value counts
                val_counts = clean_data.value_counts()
                
                # Sort the index to maintain natural order (e.g. 0,1,2,3... or [0-10), [10-20)...)
                # Instead of sorting by frequency, we sort by the labels themselves
                try:
                    val_counts = val_counts.sort_index()
                except Exception:
                    pass # If mixed types, fallback
                
                # Limit to top 30 to prevent massive charts
                if len(val_counts) > 30:
                    val_counts = clean_data.value_counts().head(30) # fallback to frequency if too many
                    
                feature_info["distribution"]["labels"] = [str(idx) for idx in val_counts.index.tolist()]
                feature_info["distribution"]["values"] = val_counts.values.tolist()
            
        report["features"][col] = feature_info
        
    print("Writing JSON report...")
    with open(output_path, 'w') as f:
        json.dump(report, f)

if __name__ == "__main__":
    base_path = "/home/sina/Downloads/data/CSE4062S26_Grp2"
    csv_file = os.path.join(base_path, "data/diabetes+130-us+hospitals+for+years+1999-2008/diabetic_data.csv")
    mapping_file = os.path.join(base_path, "data/diabetes+130-us+hospitals+for+years+1999-2008/IDS_mapping.csv")
    output_json = os.path.join(base_path, "user_tools/visualisation_tool/academic_data.json")
    
    generate_academic_report(csv_file, mapping_file, output_json)
    print("Done.")
