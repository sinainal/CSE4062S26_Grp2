import pandas as pd
import json
import os
import numpy as np

# Comprehensive and Highly Detailed Academic Dictionary for Diabetes 130-US Hospitals Dataset
FEATURE_DESCRIPTIONS = {
    "encounter_id": "Unique identifier for each admission/encounter. Useful for relational database mapping but should be removed during modeling to prevent data leakage, as it holds no clinical predictive value.",
    "patient_nbr": "Unique identifier for each patient. Crucial for identifying readmissions, as a single patient can have multiple encounters. Must be dropped before modeling to prevent the model from memorizing specific patients.",
    "race": "The racial or ethnic background of the patient (Caucasian, Asian, African American, Hispanic, or Other). Important for understanding demographic disparities in diabetes care, healthcare access, and readmission rates.",
    "gender": "The biological sex of the patient (Male, Female, or Unknown/Invalid). Used to control for biological variance in disease progression and medication efficacy.",
    "age": "Patient age, structured in 10-year ordinal intervals (e.g., [0-10), [10-20), up to [90-100)). Age is a primary risk factor for diabetes complications, healing rate, and readmission probability.",
    "weight": "The patient's weight in pounds. While clinically vital for BMI and dosage calculations, this feature is notoriously missing >95% of its data in this dataset and is typically dropped during preprocessing.",
    "admission_type_id": "Integer identifier indicating the urgency or type of admission (e.g., Emergency, Urgent, Elective). Emergency admissions often correlate with higher instability and readmission risk. (Mapped from IDS_mapping.csv)",
    "discharge_disposition_id": "Integer identifier indicating where the patient was discharged to (e.g., Home, Hospice, SNF). Crucial for filtering out terminal patients (Hospice/Expired) who logically cannot be readmitted. (Mapped from IDS_mapping.csv)",
    "admission_source_id": "Integer identifier indicating where the patient came from before admission (e.g., Emergency Room, Physician Referral, Transfer). Indicates the initial severity of the patient's condition. (Mapped from IDS_mapping.csv)",
    "time_in_hospital": "The total duration of the hospital stay in days. Longer stays generally indicate more severe complications, intensive treatments, or slower recovery, strongly influencing readmission likelihood.",
    "payer_code": "Indicates the patient's health insurance type (e.g., Medicare, Blue Cross, Self-Pay). Can serve as a proxy for socioeconomic status, which heavily impacts post-discharge care access and medication adherence.",
    "medical_specialty": "The specialty of the admitting physician (e.g., Cardiology, Internal Medicine, Surgery). Reflects the primary physiological system being treated during the encounter.",
    "num_lab_procedures": "The total number of laboratory tests performed during the patient's stay. High numbers often correlate with diagnostic uncertainty or severe, fluctuating health conditions.",
    "num_procedures": "The total number of medical procedures (excluding lab tests) performed, such as surgeries or imaging. Indicates the invasiveness and intensity of the hospital intervention.",
    "num_medications": "The number of distinct generic medications administered. Polypharmacy (high number of medications) is a known risk factor for adverse drug events and hospital readmissions.",
    "number_outpatient": "Number of outpatient visits the patient had in the year prior to this encounter. High outpatient visits may indicate proactive chronic illness management or frequent follow-ups.",
    "number_emergency": "Number of emergency room visits by the patient in the preceding year. A very strong predictor of systemic health instability, lack of primary care, and future readmissions.",
    "number_inpatient": "Number of times the patient was hospitalized in the preceding year. Historical hospitalization is statistically one of the strongest predictive features for future readmission.",
    "diag_1": "The primary ICD-9 diagnosis code that resulted in the admission. Typically requires grouping into broader clinical categories (e.g., Circulatory, Respiratory) due to extremely high cardinality.",
    "diag_2": "The secondary ICD-9 diagnosis code. Captures comorbidities that complicate the primary diagnosis. Also requires categorical grouping to be useful for machine learning models.",
    "diag_3": "An additional secondary ICD-9 diagnosis code, representing further comorbid conditions. Crucial for assessing the overall complexity of the patient's health state.",
    "number_diagnoses": "The total number of diagnoses recorded in the system for this encounter. A direct proxy for patient multimorbidity (having multiple chronic conditions) and overall health complexity.",
    "max_glu_serum": "The results of the maximum glucose serum test, if taken. Used to measure acute blood sugar levels. Values indicate normal, >200, or >300 mg/dL. 'None' means the test was not administered.",
    "A1Cresult": "The result of the HbA1c test, which measures average blood sugar over the past 2-3 months. Critical for assessing long-term diabetes control. Values include normal, >7%, or >8%.",
    "change": "A binary flag indicating whether the dosage or generic name of ANY diabetic medication was changed during the encounter. Medication changes often indicate uncontrolled diabetes requiring intervention.",
    "diabetesMed": "A binary flag indicating whether any diabetic medication was prescribed to the patient. Distinguishes between diet-controlled diabetics and medication-dependent diabetics.",
    "readmitted": "The Target Variable. Indicates if the patient was readmitted to the hospital. Classes: '<30' (within 30 days, often penalized by Medicare), '>30' (after 30 days), or 'NO' (no readmission)."
}

medications = ['metformin', 'repaglinide', 'nateglinide', 'chlorpropamide', 'glimepiride', 'acetohexamide', 'glipizide', 'glyburide', 'tolbutamide', 'pioglitazone', 'rosiglitazone', 'acarbose', 'miglitol', 'troglitazone', 'tolazamide', 'examide', 'citoglipton', 'insulin', 'glyburide-metformin', 'glipizide-metformin', 'glimepiride-pioglitazone', 'metformin-rosiglitazone', 'metformin-pioglitazone']
for med in medications:
    FEATURE_DESCRIPTIONS[med] = f"Indicates the administration status of the specific diabetic medication '{med}' during the encounter. 'Up' means the dosage was increased, 'Down' means decreased, 'Steady' means the dosage remained the same, and 'No' indicates the drug was not prescribed. Changes in these medications often signal clinical adjustments to stabilize blood glucose."

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
                        key = str(int(float(parts[0]))) 
                        val = parts[1].strip('"').strip()
                        mapping[current_map][key] = val
                    except ValueError:
                        pass
    return mapping

def generate_academic_report(csv_path, mapping_path, output_path):
    print("Loading data...")
    df_raw = pd.read_csv(csv_path, dtype=str)
    df_raw.replace('?', np.nan, inplace=True)
    
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
        raw_col = df_raw[col].dropna() 
        
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
            
        if not raw_col.empty:
            val_counts = raw_col.value_counts()
            
            if is_numeric:
                temp_numeric_index = pd.to_numeric(val_counts.index, errors='coerce')
                sorted_indices = np.argsort(temp_numeric_index.values)
                sorted_labels = val_counts.index.values[sorted_indices]
                sorted_values = val_counts.values[sorted_indices]
                
                if len(sorted_labels) > 150:
                    feature_info["distribution"]["labels"] = sorted_labels[:150].tolist()
                    feature_info["distribution"]["values"] = sorted_values[:150].tolist()
                else:
                    feature_info["distribution"]["labels"] = sorted_labels.tolist()
                    feature_info["distribution"]["values"] = sorted_values.tolist()
            else:
                sorted_indices = np.argsort(val_counts.index.values)
                sorted_labels = val_counts.index.values[sorted_indices]
                sorted_values = val_counts.values[sorted_indices]
                
                if len(sorted_labels) > 150:
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
