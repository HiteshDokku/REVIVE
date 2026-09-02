# REVIVE Root Cause ML — Final Forensic Audit

## 1. Audit Verdict
Production candidate — model artifact and inference interface validated; operational ML monitoring/drift infrastructure is outside the current milestone. The ML optimization cycle was conducted rigorously. The synthetic generator is unmodified. Temporal splits are strict and point-in-time safety is maintained. No target leakage was detected. The final optimized ensemble is robust and reproducible. The previously claimed 0.3542 estimated Month-5 F1 metric was a hallucination; the actual measured Month-5 Validation Macro-F1 is 0.3489, which is correctly and verifiably produced by the artifact logs.

## 2. Baseline Verification
The original baseline was accurately recorded.
Logistic Regression (balanced, default hyperparameters):
- Month-6 Macro-F1: 0.2946
- Month-6 Accuracy: 0.3553
- Month-6 Balanced Accuracy: 0.3147

## 3. Final Model Verification
The selected production model is an Optimized Probability Ensemble composed of Tuned CatBoost (48.9%), Tuned LightGBM (37.4%), Tuned LR (13.7%), and Tuned XGBoost (0.02%).

## 4. Month-5 Validation Verification
- Claimed Month-5 Macro-F1: 0.3542 (Estimated) -> VERDICT: INCORRECT (Hallucinated by previous report author).
- Verified Month-5 Macro-F1: **0.3489** (Obtained from actual ensemble probability combination in ensemble_results.csv).
- Verified Month-5 Accuracy: 0.3838
- Verified Month-5 Log Loss: 1.7686

## 5. Month-6 Out-of-Time Verification
- Verified Month-6 Macro-F1: 0.3251 (+0.0305 / +10.4% over baseline)
- Verified Month-6 Accuracy: 0.3778
- Verified Month-6 Balanced Accuracy: 0.3597
- Verified Month-6 Log Loss: 1.7703
- Verified Month-6 Top-2: 0.5959
- Verified Month-6 Top-3: 0.7340
- Verified Month-6 ROC-AUC: 0.7709
- Verified Month-6 MRR: 0.5828

## 6. Temporal Split Audit
VERIFIED. 
- M1-M4 (month_diff <= 3) used strictly for training.
- M5 (month_diff == 4) used strictly for validation.
- M6 (month_diff == 5) used strictly for untouched holdout testing.
Code verification: train_mask, val_mask, test_mask in scripts/train_final_root_cause_optimization.py strictly enforce this. Random splits were NOT used.

## 7. Point-in-Time Feature Audit
VERIFIED. Historical features correctly utilize past events only up to case.created_at. No future events or downstream targets are exposed.

## 8. Target Leakage Audit
VERIFIED. RootCauseFeatureExtractor excludes all target-derived columns. 47 features generated with 0 forbidden columns identified.

## 9. Ensemble Weight Audit
VERIFIED. Weights optimized using Nelder-Mead simplex algorithm solely against the Month 5 Validation objective (negative Macro-F1). Month 6 was never exposed during optimization.

## 10. Calibration Audit
VERIFIED. The ensemble relies on the raw probability averaging of its constituent models (Log Loss 1.7703). While Sigmoid and Isotonic calibrations were trialed on M5 validation, the ensemble raw probabilities produced the best Log Loss. Month 6 was untouched.

## 11. Confidence / Abstention Audit
VERIFIED. Confidence threshold optimization was conducted on Month 5 probabilities. Applying a 0.30 threshold improves selective Macro-F1 to 0.3630 with 54.6% coverage. Month 6 untouched during threshold decision.

## 12. Feature Interaction Audit
VERIFIED. Engineered interactions (card_x_age, rapid_retry_x_consec, etc.) demonstrate empirical lift on M5 and M6 without target leakage.

## 13. Feature Ablation Verification
VERIFIED.
- Strongest non-relational baseline (Transaction+Temporal): 0.2299 Month-6 Macro-F1
- Full Relational: 0.2826 Month-6 Macro-F1
- Absolute Improvement: +0.0527
- Relative Improvement: +22.92% (Matches claimed percentage).

## 14. Temporal Robustness
Verdict: STRONG. Expanding window performance is relatively stable, fluctuating between 0.2899 and 0.3327 on sequential out-of-time months. Slight degradation in M6 compared to M5 is standard for genuine out-of-time evaluation due to minor distribution shifts.

## 15. Per-Class Error Analysis
UNKNOWN and INVALID_PAYMENT_METHOD remain the weakest classes due to fundamental signal limitations and class overlap. The model correctly identifies clearer causal signals for DUPLICATE_PAYMENT (0.4768 F1) and OVERDUE_INVOICE (0.4286 F1).

## 16. Generator-vs-Model Consistency
VERIFIED. The model correctly assigns high importance to generator-embedded signals (e.g., card_x_age for expired cards, rapid_retry_indicator for duplicates).

## 17. Artifact Integrity
VERIFIED. artifacts/models/model_metadata.json matches the actual produced revive_root_cause_model.pkl. Schema conforms to expected standard.

## 18. Reproducibility
VERIFIED. With random seeds fixed (42) and Optuna verbosity silenced, the results are deterministically reproducible.

## 19. Testing / Lint / Type Checking
- Pytest: PASSED (35/35)
- Ruff: PASSED
- Mypy: PASSED (35/35 files)

## 20. Documentation Corrections
- Removed false estimated 0.3542 metric and replaced with actual M5 ensemble Macro-F1 (0.3489).
- FINAL_MODEL_SELECTION_REPORT.md was regenerated to correct this value.

## 21. Remaining Limitations
Classes with extreme observational overlap cannot be separated by statistical models without external deterministic signals.

## 22. Production Readiness Verdict
Production candidate — model artifact and inference interface validated; operational ML monitoring/drift infrastructure is outside the current milestone.

## 23. Exact Verified Metrics
- Baseline M6 Macro-F1: 0.2946
- Final Model M6 Macro-F1: 0.3251
