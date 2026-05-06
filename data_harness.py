import pandas as pd
import numpy as np

def load_and_clean_data(file_path):
    print("Loading data...")
    df = pd.read_csv(file_path, na_values=['?'])
    
    print(f"Original shape: {df.shape}")
    
    # ==========================================
    # PHASE 1: Record Filtering
    # ==========================================
    
    # 1. Keep only the first encounter per patient to avoid data leakage
    df = df.sort_values('encounter_id').drop_duplicates(subset=['patient_nbr'], keep='first')
    print(f"Shape after removing duplicate encounters: {df.shape}")
    
    # 2. Remove terminal discharges (Death or Hospice)
    # IDs: 11, 13, 14, 19, 20, 21
    terminal_ids = [11, 13, 14, 19, 20, 21]
    df = df[~df['discharge_disposition_id'].isin(terminal_ids)]
    print(f"Shape after removing terminal discharges: {df.shape}")
    
    # ==========================================
    # PHASE 2: Dimensionality Reduction & Feature Engineering
    # ==========================================
    
    # 3. Target Variable Binarization
    # 1 if <30 days, 0 otherwise (>30 or NO)
    df['readmitted_binary'] = (df['readmitted'] == '<30').astype(int)
    df = df.drop(columns=['readmitted'])
    
    # 4. Drop highly sparse columns and IDs
    df = df.drop(columns=['weight', 'payer_code', 'encounter_id', 'patient_nbr'])
    
    # 5. Handle missing values
    df['medical_specialty'] = df['medical_specialty'].fillna('Missing')
    df['race'] = df['race'].fillna('Unknown')
    
    # Fill remaining missing diagnoses with 'Missing'
    df['diag_1'] = df['diag_1'].fillna('Missing')
    df['diag_2'] = df['diag_2'].fillna('Missing')
    df['diag_3'] = df['diag_3'].fillna('Missing')
    
    # 6. ICD-9 Diagnosis Grouping
    def map_icd9(val):
        if val == 'Missing':
            return 'Missing'
        if str(val).startswith('V') or str(val).startswith('E'):
            return 'Other'
        try:
            # Handle float strings like '250.01'
            num = float(val)
            if 390 <= num <= 459 or num == 785:
                return 'Circulatory'
            elif 460 <= num <= 519 or num == 786:
                return 'Respiratory'
            elif 520 <= num <= 579 or num == 787:
                return 'Digestive'
            elif np.floor(num) == 250:
                return 'Diabetes'
            elif 800 <= num <= 999:
                return 'Injury'
            elif 710 <= num <= 739:
                return 'Musculoskeletal'
            elif 580 <= num <= 629 or num == 788:
                return 'Genitourinary'
            elif 140 <= num <= 239:
                return 'Neoplasms'
            else:
                return 'Other'
        except ValueError:
            return 'Other'

    for col in ['diag_1', 'diag_2', 'diag_3']:
        df[col + '_group'] = df[col].apply(map_icd9)
    df = df.drop(columns=['diag_1', 'diag_2', 'diag_3'])
    
    # 7. Age Transformation
    # Convert '[40-50)' to 45
    age_mapping = {
        '[0-10)': 5, '[10-20)': 15, '[20-30)': 25, '[30-40)': 35, 
        '[40-50)': 45, '[50-60)': 55, '[60-70)': 65, '[70-80)': 75, 
        '[80-90)': 85, '[90-100)': 95
    }
    df['age'] = df['age'].map(age_mapping)
    
    # 8. Medication Compression
    medication_cols = [
        'metformin', 'repaglinide', 'nateglinide', 'chlorpropamide', 
        'glimepiride', 'acetohexamide', 'glipizide', 'glyburide', 
        'tolbutamide', 'pioglitazone', 'rosiglitazone', 'acarbose', 
        'miglitol', 'troglitazone', 'tolazamide', 'examide', 
        'citoglipton', 'insulin', 'glyburide-metformin', 
        'glipizide-metformin', 'glimepiride-pioglitazone', 
        'metformin-rosiglitazone', 'metformin-pioglitazone'
    ]
    
    # Count how many medications were Up or Down
    df['num_medications_changed'] = df[medication_cols].apply(
        lambda row: sum(row.isin(['Up', 'Down'])), axis=1
    )
    
    # Drop the original sparse medication columns
    df = df.drop(columns=medication_cols)
    
    # 9. Admission/Discharge Mapping (Simplification)
    # Collapse Discharge Disposition
    df['discharge_home'] = df['discharge_disposition_id'].isin([1, 6, 8]).astype(int)
    
    print(f"Final shape before saving: {df.shape}")
    print(f"Readmission Rate (<30 days): {df['readmitted_binary'].mean():.4f}")
    
    return df

if __name__ == "__main__":
    input_file = '/home/sina/Downloads/data/CSE4062S26_Grp2/data/diabetes+130-us+hospitals+for+years+1999-2008/diabetic_data.csv'
    output_file = '/home/sina/Downloads/data/CSE4062S26_Grp2/data/cleaned_diabetic_data.csv'
    
    cleaned_df = load_and_clean_data(input_file)
    cleaned_df.to_csv(output_file, index=False)
    print(f"Data saved to {output_file}")
