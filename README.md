# Diabetes Readmission Research Project (Grp2)

## 📊 Project Overview
This repository contains an academic-grade data science pipeline for the **Diabetes 130-US Hospitals (1999-2008)** dataset. Our objective is to predict 30-day hospital readmission using advanced feature engineering and machine learning, grounded in original clinical research.

## Quick Start
From the project root, run:

```bash
bash start.sh
```

This will:
- open the dashboard on port `8081` by default,
- reuse existing JSON reports unless `REFRESH_DATA=1` is set,
- regenerate the outputs only when they are missing or explicitly requested.

If you only want to serve the dashboard after preprocessing is already done:

```bash
python3 -m http.server 8081 --directory user_tools/visualisation_tool
```

## 🛠 Clinical Analysis Tool
We have developed a custom **Clinical Visualization & Discovery Tool** located in `/user_tools/visualisation_tool/`. 
- **Features:** Real-time distribution analysis, Z-score based outlier highlighting, and dynamic clinical record browsing.
- **ICD-9 Integration:** The tool now features a live mapping of 14,000+ ICD-9 codes to their full clinical descriptions via interactive tooltips.
- **Model-Ready Dataset View:** The dashboard includes a dedicated section that previews the actual one-hot encoded, standardized modeling table.
- **Baseline ML Test:** A simple Logistic Regression baseline is trained directly on the model-ready dataset as a sanity check before adding stronger models.
- **Model Comparison:** The dashboard now includes feature selection rankings, ROC curves, and significance comparison for the strongest predictive models.
- **Descriptive Mining:** The clustering lab compares K-Means, hierarchical clustering, and DBSCAN, and the association-mining page summarizes Apriori-style rules.
- **Usage:** Run `bash start.sh` from the project root to open the app. Set `REFRESH_DATA=1` if you want to regenerate the reports first.

## 🧼 Data Preprocessing & Cleaning (Core Methodology)
Our preprocessing strategy is strictly aligned with the original **Strack et al. (2014)** study and modern ML best practices (2024). The logic is implemented in `data_harness.py`.

### 1. Record Filtering & Independence
- **First Encounters Only:** To ensure statistical independence and avoid data leakage, we retain only the first hospital encounter for each patient ID.
- **Terminal Discharge Removal:** Based on the `IDS_mapping.csv` (IDs 11, 13, 14, 19, 20, 21), we exclude all encounters where the patient died or was discharged to a hospice.

### 2. Feature Engineering
- **Target Variable:** Binarized into `1` (Readmitted <30 days) and `0` (Otherwise).
- **High-Cardinality Mapping:** 900+ ICD-9 diagnosis codes are grouped into 9 primary clinical categories (Circulatory, Respiratory, etc.).
- **Age Decodification:** Age brackets (e.g., `[40-50)`) are converted to numerical midpoints for algorithmic processing.
- **Medication Complexity:** 24 medication columns are condensed into a `num_medications_changed` feature to capture clinical instability.

### 3. Data Integrity
- **Weight/Payer Code:** Removed due to excessive missingness (>40-97%).
- **Medical Specialty:** Preserved by mapping missing values to a distinct 'Missing' category, as clinical literature suggests "missingness" in specialty can be a proxy for emergency urgency.
- **Clinical "None" Values:** HbA1c and glucose serum values of `None` are preserved as meaningful "test not performed" categories, not treated as missing cells.

### 4. Model-Ready Output
- `data/model_ready_diabetic_data.csv` contains the fully transformed dataset used for modeling.
- Numeric features are median-imputed and standardized.
- Categorical features are mode-imputed and one-hot encoded.
- The target column is `readmitted`, where `<30` is encoded as `1` and all other outcomes as `0`.
- `user_tools/visualisation_tool/model_ready_data.json` powers the dashboard preview and transformation report.

### 5. Baseline Modeling
- `data_harness.py` trains a class-balanced Logistic Regression baseline after generating the model-ready table.
- Results are exported to `user_tools/visualisation_tool/baseline_model_report.json`.
- This baseline is intentionally simple; future work can add XGBoost, LightGBM, CatBoost, and calibrated threshold tuning.

## 📂 Repository Structure
- `/data/`: Raw and cleaned datasets.
- `/user_tools/visualisation_tool/`: Interactive analysis dashboard.
- `data_harness.py`: The primary preprocessing engine.
- `start.sh`: Convenience script that runs preprocessing and launches the local dashboard.
- `articles/`: Local library of relevant academic papers.

---
*Developed for the Spring 2026 Data Science Course Project.*
