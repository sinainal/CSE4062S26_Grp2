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
    "admission_type_id": "Integer identifier. Hover over chart bars to see mapping.",
    "discharge_disposition_id": "Integer identifier. Hover over chart bars to see mapping.",
    "admission_source_id": "Integer identifier. Hover over chart bars to see mapping.",
    "time_in_hospital": "Integer number of days between admission and discharge.",
    "payer_code": "Integer identifier corresponding to 23 distinct values.",
    "medical_specialty": "Integer identifier of a specialty of the admitting physician.",
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
    "max_glu_serum": "Indicates the range of the result or if the test was not taken.",
    "A1Cresult": "Indicates the range of the result or if the test was not taken.",
    "change": "Indicates if there was a change in diabetic medications.",
    "diabetesMed": "Indicates if there was any diabetic medication prescribed.",
    "readmitted": "Target Variable: Days to inpatient readmission."
}

medications = ['metformin', 'repaglinide', 'nateglinide', 'chlorpropamide', 'glimepiride', 'acetohexamide', 'glipizide', 'glyburide', 'tolbutamide', 'pioglitazone', 'rosiglitazone', 'acarbose', 'miglitol', 'troglitazone', 'tolazamide', 'examide', 'citoglipton', 'insulin', 'glyburide-metformin', 'glipizide-metformin', 'glimepiride-pioglitazone', 'metformin-rosiglitazone', 'metformin-pioglitazone']
for med in medications:
    FEATURE_DESCRIPTIONS[med] = f"Indicates whether the drug {med} was prescribed. Values: 'up', 'down', 'steady', and 'no'."

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
                        # Extract integer explicitly
                        key = str(int(float(parts[0]))) 
                        val = parts[1].strip('"').strip()
                        mapping[current_map][key] = val
                    except ValueError:
                        pass
    return mapping

def generate_academic_report(csv_path, mapping_path, output_path):
    print("Loading data...")
    # Load EXACTLY as strings first to prevent Pandas from converting integers to floats if NaNs are present.
    # This prevents '1' becoming '1.0' on the X-axis.
    df_raw = pd.read_csv(csv_path, dtype=str)
    df_raw.replace('?', np.nan, inplace=True)
    
    # We also need a typed version for statistics (mean, std, etc)
    df_typed = pd.read_csv(csv_path, na_values=['?'])
    
    mappings = load_ids_mapping(mapping_path)
    
    report = {
        "dataset_overview": {},
        "raw_sample": [],
        "features": {}
    }
    
    report["dataset_overview"]["total_rows"] = len(df_typed)
    report["dataset_overview"]["total_cols"] = len(df_typed.columns)
    report["dataset_overview"]["total_missing_cells"] = int(df_typed.isna().sum().sum())
    report["dataset_overview"]["duplicate_rows"] = int(df_typed.duplicated().sum())
    
    sample_df = df_typed.head(100).replace({np.nan: None})
    report["raw_sample"] = sample_df.to_dict(orient='records')
    
    for col in df_typed.columns:
        typed_col = df_typed[col]
        raw_col = df_raw[col].dropna() # EXACT string values from CSV
        
        is_numeric = pd.api.types.is_numeric_dtype(typed_col)
        
        missing_count = int(typed_col.isna().sum())
        missing_pct = round((missing_count / len(df_typed)) * 100, 2)
        unique_count = int(raw_col.nunique())
        
        feature_info = {
            "name": col,
            "description": FEATURE_DESCRIPTIONS.get(col, "No detailed description available."),
            "type": "Numeric" if is_numeric else "Categorical",
            "missing_count": missing_count,
            "missing_pct": missing_pct,
            "unique_count": unique_count,
            "stats": {},
            "distribution": {},
            "value_mapping": mappings.get(col, {}),
            "cleaning_method": "Keep",
            "cleaning_explanation": ""
        }
        
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

        clean_typed = typed_col.dropna()
        if is_numeric:
            feature_info["stats"]["mean"] = round(float(clean_typed.mean()), 4) if not clean_typed.empty else None
            feature_info["stats"]["std"] = round(float(clean_typed.std()), 4) if not clean_typed.empty else None
            feature_info["stats"]["min"] = float(clean_typed.min()) if not clean_typed.empty else None
            feature_info["stats"]["q25"] = float(clean_typed.quantile(0.25)) if not clean_typed.empty else None
            feature_info["stats"]["median"] = float(clean_typed.median()) if not clean_typed.empty else None
            feature_info["stats"]["q75"] = float(clean_typed.quantile(0.75)) if not clean_typed.empty else None
            feature_info["stats"]["max"] = float(clean_typed.max()) if not clean_typed.empty else None
            
        # --- ZERO ASSUMPTION DISTRIBUTION GENERATION ---
        # 1. Get raw exact value counts as strings to preserve format. No np.histogram.
        if not raw_col.empty:
            val_counts = raw_col.value_counts()
            
            # 2. To sort correctly, check if the raw strings can be parsed to floats.
            if is_numeric:
                # Create a temporary numeric series to sort by the true numerical value
                temp_numeric_index = pd.to_numeric(val_counts.index, errors='coerce')
                # Sort using the numeric index
                sorted_indices = np.argsort(temp_numeric_index.values)
                sorted_labels = val_counts.index.values[sorted_indices]
                sorted_values = val_counts.values[sorted_indices]
                
                # Take top 100 maximum to prevent browser crash, but it will be EXACT values.
                if len(sorted_labels) > 150:
                    feature_info["distribution"]["labels"] = sorted_labels[:150].tolist()
                    feature_info["distribution"]["values"] = sorted_values[:150].tolist()
                else:
                    feature_info["distribution"]["labels"] = sorted_labels.tolist()
                    feature_info["distribution"]["values"] = sorted_values.tolist()
            else:
                # For categoricals, sort by the exact string label alphabetically.
                sorted_indices = np.argsort(val_counts.index.values)
                sorted_labels = val_counts.index.values[sorted_indices]
                sorted_values = val_counts.values[sorted_indices]
                
                if len(sorted_labels) > 150:
                    # If too many categories (like diag_1), fallback to frequency sort so top 50 are shown
                    val_counts = raw_col.value_counts().head(50)
                    feature_info["distribution"]["labels"] = val_counts.index.tolist()
                    feature_info["distribution"]["values"] = val_counts.values.tolist()
                else:
                    feature_info["distribution"]["labels"] = sorted_labels.tolist()
                    feature_info["distribution"]["values"] = sorted_values.tolist()
            
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
