# App Final Workflow Report

Date: 2026-05-07

This document summarizes the current end-to-end behavior of the `CSE4062S26_Grp2` application as it exists in the latest dashboard-focused version of the repo.

## 1. Overall Flow

The project now behaves like a reproducible local analytics app:

1. `start.sh` bootstraps a local Python virtual environment if needed.
2. It installs dependencies only when `requirements.txt` changes.
3. It checks whether preprocessing outputs and dashboard JSON caches already exist.
4. If any required artifact is missing, it regenerates the data pipeline outputs.
5. It starts the visualization server and opens the dashboard in the browser.

The important design choice is that the app does not blindly rerun the whole pipeline on every launch. If the cached outputs are already present, startup is fast and the dashboard opens directly.

## 2. Startup Behavior

The startup script currently handles:

- virtual environment creation
- dependency installation
- port selection with fallback when the default port is busy
- optional browser opening
- regeneration of preprocessing and analytics outputs when needed
- server launch and basic readiness check

Key behavior:

- Default port: `8081`
- If that port is busy, the script searches for the next free port.
- If `REFRESH_DATA=1` is set, the pipeline is regenerated.
- If required CSV/JSON outputs are missing, the pipeline is regenerated automatically.

Relevant file:

- [`start.sh`](/home/sina/Downloads/data/CSE4062S26_Grp2/start.sh)

## 3. Data Pipeline

The core data pipeline lives in `data_harness.py`.

### 3.1 Raw Data Loading

The raw UCI diabetes dataset is read from:

- `data/diabetes+130-us+hospitals+for+years+1999-2008/diabetic_data.csv`

Current dataset sizes in the repo:

- Raw dataset: `101,766` rows, `50` columns
- Cleaned dataset: `69,970` rows
- Model-ready dataset: `69,970` rows, `160` columns

### 3.2 Cleaning Steps

The cleaning stage currently does the following:

- removes repeated patient encounters by keeping the first encounter per patient
- removes terminal discharge records that cannot support a readmission prediction
- removes invalid gender rows
- computes near-zero variance statistics for medication fields
- drops low-information medication columns
- fills missing values for selected clinical fields with human-readable categories

This step produces:

- `data/cleaned_diabetic_data.csv`
- `user_tools/visualisation_tool/cleaning_data.json`
- `user_tools/visualisation_tool/nzv_report.json`
- `user_tools/visualisation_tool/full_nzv_report.json`

Relevant file:

- [`data_harness.py`](/home/sina/Downloads/data/CSE4062S26_Grp2/data_harness.py)

### 3.3 Model-Ready Transformation

The cleaned clinical table is then transformed into a model-ready matrix by:

- adding medication change counts
- dropping leakage and high-missing columns
- converting age bands into numeric midpoints
- grouping ICD-9 diagnosis codes into broader clinical categories
- binarizing the readmission target
- applying median imputation to numeric fields
- applying most-frequent imputation to categorical fields
- one-hot encoding categorical variables
- standardizing numeric variables

This stage produces:

- `data/model_ready_diabetic_data.csv`
- `user_tools/visualisation_tool/model_ready_data.json`

## 4. Predictive Analytics

The app includes two predictive layers:

1. baseline model comparison
2. interactive live model lab

### 4.1 Baseline Model Comparison

The baseline page trains multiple classifiers on the same stratified 80/20 split of the full model-ready dataset.

Current baseline models:

- Logistic Regression
- Random Forest
- Gradient Boosting
- XGBoost, if available

The baseline report includes:

- confusion matrix
- TN, FP, FN, TP counts
- ROC curves
- class balance
- best model selection
- closest competitor
- significance analysis using McNemar
- feature signal tables for the strongest interpretable model

This is the main place where the dashboard shows formal classification comparison.

Relevant files:

- [`data_harness.py`](/home/sina/Downloads/data/CSE4062S26_Grp2/data_harness.py)
- [`user_tools/visualisation_tool/baseline_model_report.json`](/home/sina/Downloads/data/CSE4062S26_Grp2/user_tools/visualisation_tool/baseline_model_report.json)
- [`user_tools/visualisation_tool/app.js`](/home/sina/Downloads/data/CSE4062S26_Grp2/user_tools/visualisation_tool/app.js)

### 4.2 Feature Selection

Feature selection now runs on the full stratified training split, not on a pre-truncated sample.

Implemented methods:

- Mutual Information
- Chi-square
- Random Forest importance
- Absolute Logistic Regression coefficients
- RFE with Logistic Regression
- Consensus ranking across methods

The report stores:

- method-wise top features
- top-20 selected feature sets
- split sizes

Relevant file:

- [`data_harness.py`](/home/sina/Downloads/data/CSE4062S26_Grp2/data_harness.py)
- [`user_tools/visualisation_tool/feature_selection_report.json`](/home/sina/Downloads/data/CSE4062S26_Grp2/user_tools/visualisation_tool/feature_selection_report.json)

### 4.3 Feature-Subset Experiments

The subset experiments retrain Logistic Regression and Random Forest on selected feature groups derived from feature selection.

This produces a structured comparison of:

- feature set name
- model name
- feature count
- ROC-AUC
- accuracy
- recall
- F1

Relevant file:

- [`user_tools/visualisation_tool/feature_subset_report.json`](/home/sina/Downloads/data/CSE4062S26_Grp2/user_tools/visualisation_tool/feature_subset_report.json)

### 4.4 Regression

Regression is implemented as an optional but now fully included task.

Current regression target:

- `time_in_hospital`

Models compared:

- Linear Regression
- Ridge Regression
- Random Forest Regressor
- Gradient Boosting Regressor
- XGBoost Regressor, if available

The regression report includes:

- MAE
- RMSE
- R2
- residual summary
- prediction sample
- positive and negative feature signals

This task now uses the full cleaned/model-ready dataset rather than a hard cap sample.

Relevant file:

- [`data_harness.py`](/home/sina/Downloads/data/CSE4062S26_Grp2/data_harness.py)
- [`user_tools/visualisation_tool/regression_report.json`](/home/sina/Downloads/data/CSE4062S26_Grp2/user_tools/visualisation_tool/regression_report.json)

## 5. Interactive Live Model Lab

The Live Model Lab is one of the main strengths of the app.

### 5.1 What It Does

Users can:

- choose an algorithm
- adjust hyperparameters
- choose a dataset size mode
- run an experiment directly from the browser
- inspect the resulting confusion matrix, ROC curve, metrics, and run history

### 5.2 Dataset Size Modes

The app supports four live experiment modes:

- `Auto safe`
- `Fast sample`
- `Medium sample`
- `Full split`

These modes control how much of the stratified train/test split is used for the live run.

Current behavior:

- `Fast sample` is the quickest interactive option.
- `Medium sample` is the default precomputed reference level.
- `Auto safe` uses a larger safe subset for classroom use.
- `Full split` uses the whole 80/20 split and may take longer for heavier algorithms.

### 5.3 Current Algorithms

The live lab currently supports:

- k-NN
- Naive Bayes
- Decision Tree
- Random Forest
- XGBoost
- MLP
- SVM (RBF)

The UI keeps a recent run history for each algorithm and lets the user inspect the best run or any previously executed configuration.

Relevant files:

- [`user_tools/visualisation_tool/server.py`](/home/sina/Downloads/data/CSE4062S26_Grp2/user_tools/visualisation_tool/server.py)
- [`user_tools/visualisation_tool/app.js`](/home/sina/Downloads/data/CSE4062S26_Grp2/user_tools/visualisation_tool/app.js)
- [`user_tools/visualisation_tool/model_lab_report.json`](/home/sina/Downloads/data/CSE4062S26_Grp2/user_tools/visualisation_tool/model_lab_report.json)

## 6. Descriptive Analytics

The descriptive side of the app contains:

- K-Means clustering
- hierarchical clustering
- DBSCAN
- Apriori association mining

### 6.1 Clustering

Clustering is done on a PCA projection of the model-ready matrix.

The app compares:

- K-Means for `k = 2..8`
- hierarchical clustering for `k = 2..8`
- DBSCAN over several `eps` and `min_samples` combinations

The dashboard shows:

- sample size
- full dataset size
- PCA explained variance
- silhouette score
- cluster summaries
- readmission rates per cluster
- a 2D scatter view with selectable color modes

Important note:

- Clustering is intentionally sampled for browser responsiveness.
- This is documented in the app so the limitation is explicit rather than hidden.

Relevant file:

- [`user_tools/visualisation_tool/clustering_report.json`](/home/sina/Downloads/data/CSE4062S26_Grp2/user_tools/visualisation_tool/clustering_report.json)

### 6.2 Apriori Association Mining

Apriori-style rule mining uses interpretable clinical fields and a capped transaction sample.

The report includes:

- total transactions
- frequent itemsets
- mined rules
- support and confidence thresholds
- sample row count
- full cleaned row count
- a warning explaining why the sample cap exists

Important note:

- This stage remains sampled by design because full Apriori expansion becomes expensive and noisy on the entire table.

Relevant file:

- [`user_tools/visualisation_tool/association_rules_report.json`](/home/sina/Downloads/data/CSE4062S26_Grp2/user_tools/visualisation_tool/association_rules_report.json)

## 7. Dashboard Pages

The app is organized into multiple browser pages:

1. Raw data browser
2. Cleaning browser
3. Model-ready browser
4. Baseline ML test page
5. Regression page
6. Live Model Lab
7. Clustering Lab
8. Association Mining page
9. Conclusion page

The dashboard also includes:

- feature drill-down views
- log-scale toggles
- confusion matrix tables
- ROC charts
- feature ranking tables
- experiment inventories
- summary cards and explanatory notes

Relevant files:

- [`user_tools/visualisation_tool/index.html`](/home/sina/Downloads/data/CSE4062S26_Grp2/user_tools/visualisation_tool/index.html)
- [`user_tools/visualisation_tool/app.js`](/home/sina/Downloads/data/CSE4062S26_Grp2/user_tools/visualisation_tool/app.js)
- [`user_tools/visualisation_tool/style.css`](/home/sina/Downloads/data/CSE4062S26_Grp2/user_tools/visualisation_tool/style.css)

## 8. Current Strengths

The present version of the app is strongest in these areas:

- One-command startup
- Automatic dependency bootstrap
- Reproducible cached outputs
- Interactive live experiment reruns
- Clear confusion matrix reporting with TN/FP/FN/TP
- Baseline significance comparison
- Full regression support
- Explicit dataset size reporting in the lab
- Honest warnings for sample-based descriptive methods

## 9. Current Constraints

The app still has a few intentional or strategic constraints:

- Clustering is sampled for practicality and visualization quality.
- Apriori is sampled to keep rule generation manageable.
- Full raw data is still present in the repo and should be reviewed against submission policy.
- The repo is still more dashboard-centric than script-centric, so standalone wrapper scripts would still improve the final submission package.

## 10. Practical Summary

If you open the project today, the intended experience is:

1. `start.sh` creates or reuses the local environment.
2. It verifies that preprocessing and cached analytics files exist.
3. It refreshes the data artifacts only when needed.
4. It launches the dashboard.
5. The dashboard loads the prepared reports and allows interactive reruns in the live lab.

That is the current operational shape of the project: a reproducible, presentation-ready analytics app with both precomputed results and interactive experiment reruns.
