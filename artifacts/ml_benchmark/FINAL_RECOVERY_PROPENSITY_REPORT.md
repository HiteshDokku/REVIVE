# FINAL MODEL SELECTION REPORT: Recovery Propensity Model (Optimized)

## 1. Objective
Maximize out-of-time predictive performance for `P(recovery | case context, candidate action)` ensuring strict causal and temporal integrity.

## 2. Dataset & Features
* Total generated interventions: 138104
* Baseline recovery rate: 19.71%
* Temporal Split: M1-M4 (Train), M5 (Validation), M6 (Test)
* **New Features Added:** Non-linear attempt interactions (`attempt_number_sq`), Economic Ratios (`amount_to_ltv_ratio`), Granular causal interactions.

## 3. Model Search & Selection
* **Models Evaluated:** XGBoost (Optuna), LightGBM (Optuna), CatBoost.
* **Selected Model:** Calibrated LGBM
* **Optimal Classification Threshold:** 0.35

## 4. Final Evaluation (Month-6 Test)
* **ROC-AUC:** 0.8647
* **PR-AUC:** 0.6182
* **Brier Score:** 0.1074
* **Log Loss:** 0.3361
* **F1-Score:** 0.5560
* **Accuracy:** 0.8305
* **Expected Value Estimation Improvement:** +1,631,485.07 (6.12%) over a Global Average Probability baseline.

## 5. Target Leakage Audit
PASSED - Validated zero target-derived features in training path.
