import pandas as pd
import json
import os
import numpy as np

def analyze_data(csv_path, output_path):
    df = pd.read_csv(csv_path)
    
    # Replace '?' with NaN for analysis
    df.replace('?', np.nan, inplace=True)
    
    summary = {
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "columns": {}
    }
    
    for col in df.columns:
        col_data = df[col]
        dtype = str(col_data.dtype)
        missing_count = col_data.isna().sum()
        unique_values = col_data.nunique()
        
        stats = {
            "dtype": dtype,
            "missing_pct": round((missing_count / len(df)) * 100, 2),
            "unique_count": int(unique_values),
        }
        
        is_numeric = pd.api.types.is_numeric_dtype(col_data)
        
        if is_numeric:
            # Numerical stats
            stats["type"] = "numerical"
            stats["min"] = float(col_data.min()) if not col_data.isna().all() else 0
            stats["max"] = float(col_data.max()) if not col_data.isna().all() else 0
            stats["mean"] = float(col_data.mean()) if not col_data.isna().all() else 0
            
            # For distribution (histogram)
            hist, bin_edges = np.histogram(col_data.dropna(), bins=10)
            stats["distribution"] = {
                "labels": [f"{bin_edges[i]:.1f}-{bin_edges[i+1]:.1f}" for i in range(len(hist))],
                "values": hist.tolist()
            }
        else:
            # Categorical stats
            stats["type"] = "categorical"
            top_values = col_data.value_counts().head(10)
            stats["distribution"] = {
                "labels": top_values.index.tolist(),
                "values": top_values.values.tolist()
            }
            
        summary["columns"][col] = stats
        
    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=4)

if __name__ == "__main__":
    base_path = "/home/sina/Downloads/data/CSE4062S26_Grp2"
    csv_file = os.path.join(base_path, "data/diabetes+130-us+hospitals+for+years+1999-2008/diabetic_data.csv")
    output_json = os.path.join(base_path, "user_tools/visualisation_tool/data_summary.json")
    
    print(f"Analyzing {csv_file}...")
    analyze_data(csv_file, output_json)
    print(f"Analysis complete. Summary saved to {output_json}")
