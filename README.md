# Diabetes Readmission Research Project (Grp2)

## 📊 Project Overview
This repository contains an academic-grade data science pipeline for the **Diabetes 130-US Hospitals (1999-2008)** dataset. Our objective is to predict 30-day hospital readmission using advanced feature engineering and machine learning, grounded in original clinical research.

## 🛠 Clinical Analysis Tool
We have developed a custom **Clinical Visualization & Discovery Tool** located in `/user_tools/visualisation_tool/`. 
- **Features:** Real-time distribution analysis, Z-score based outlier highlighting, and dynamic clinical record browsing.
- **ICD-9 Integration:** The tool now features a live mapping of 14,000+ ICD-9 codes to their full clinical descriptions via interactive tooltips.
- **Usage:** Run `python3 -m http.server 8000` in the tool directory to access the dashboard.

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

## 📂 Repository Structure
- `/data/`: Raw and cleaned datasets.
- `/user_tools/visualisation_tool/`: Interactive analysis dashboard.
- `data_harness.py`: The primary preprocessing engine.
- `articles/`: Local library of relevant academic papers.

---
*Developed for the Spring 2026 Data Science Course Project.*
