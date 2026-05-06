import pandas as pd
import json
import os
import numpy as np

def generate_academic_report(csv_path, output_path):
    print("Loading data...")
    df = pd.read_csv(csv_path)
    
    # Replace '?' with NaN to accurately count missing values
    df.replace('?', np.nan, inplace=True)
    
    report = {
        "dataset_overview": {},
        "raw_sample": [],
        "features": {}
    }
    
    # 1. Dataset Overview
    report["dataset_overview"]["total_rows"] = len(df)
    report["dataset_overview"]["total_cols"] = len(df.columns)
    report["dataset_overview"]["total_missing_cells"] = int(df.isna().sum().sum())
    report["dataset_overview"]["duplicate_rows"] = int(df.duplicated().sum())
    
    # 2. Raw Sample (first 100 rows for the raw data panel)
    # Convert NaN to None for JSON serialization
    sample_df = df.head(100).replace({np.nan: None})
    report["raw_sample"] = sample_df.to_dict(orient='records')
    
    # 3. Features Detail
    for col in df.columns:
        col_data = df[col]
        is_numeric = pd.api.types.is_numeric_dtype(col_data)
        
        missing_count = int(col_data.isna().sum())
        missing_pct = round((missing_count / len(df)) * 100, 2)
        unique_count = int(col_data.nunique(dropna=True))
        
        feature_info = {
            "name": col,
            "type": "Numeric" if is_numeric else "Categorical",
            "missing_count": missing_count,
            "missing_pct": missing_pct,
            "unique_count": unique_count,
            "stats": {},
            "distribution": {},
            "academic_note": ""
        }
        
        # Academic / Preprocessing Note Generation
        notes = []
        if missing_pct > 40:
            notes.append(f"Severe missingness ({missing_pct}%). Candidates for omission unless theoretically critical.")
        elif missing_pct > 5:
            notes.append(f"Moderate missingness ({missing_pct}%). Requires imputation strategy (e.g., median/mode imputation or predictive modeling).")
            
        if unique_count == 1:
            notes.append("Zero variance variable. Provides no discriminatory power; recommend removal.")
        elif unique_count == len(df):
            notes.append("High cardinality/Identifier variable. Unlikely to generalize; recommend removal or transformation.")
            
        if col in ['diag_1', 'diag_2', 'diag_3']:
            notes.append("ICD-9 diagnosis codes. Highly granular; requires aggregation into broader clinical categories (e.g., circulatory, respiratory).")
            
        feature_info["academic_note"] = " ".join(notes) if notes else "Standard variable. Appears structurally sound for baseline modeling."
        
        if is_numeric:
            clean_data = col_data.dropna()
            feature_info["stats"]["mean"] = round(float(clean_data.mean()), 4) if not clean_data.empty else None
            feature_info["stats"]["std"] = round(float(clean_data.std()), 4) if not clean_data.empty else None
            feature_info["stats"]["min"] = float(clean_data.min()) if not clean_data.empty else None
            feature_info["stats"]["q25"] = float(clean_data.quantile(0.25)) if not clean_data.empty else None
            feature_info["stats"]["median"] = float(clean_data.median()) if not clean_data.empty else None
            feature_info["stats"]["q75"] = float(clean_data.quantile(0.75)) if not clean_data.empty else None
            feature_info["stats"]["max"] = float(clean_data.max()) if not clean_data.empty else None
            
            # Histogram bins
            if not clean_data.empty:
                hist, bin_edges = np.histogram(clean_data, bins=20)
                feature_info["distribution"]["labels"] = [f"{bin_edges[i]:.2f}" for i in range(len(hist))]
                feature_info["distribution"]["values"] = hist.tolist()
        else:
            # Categorical stats
            clean_data = col_data.dropna()
            top_counts = clean_data.value_counts().head(15)
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
