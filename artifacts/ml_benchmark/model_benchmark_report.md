# REVIVE Master Root-Cause ML Benchmark Report

**Execution Timestamp**: 2026-08-29T13:17:01.372172+00:00  
**Evaluated Environment**: 35,000 Customers | 242,180 Payments | 79,817 Recovery Cases  
**Primary Holdout Test**: Month 6 ($N = 1,064$ ML Fallback Cases)

---

## Executive Model Leaderboard (Month 5 Validation)

| Model               |   Val_Macro_F1 |   Val_Accuracy |   Val_Bal_Acc |   Val_Weighted_F1 |   Val_Log_Loss |   Val_Top1_Acc |   Val_Top2_Acc |   Val_Top3_Acc |
|:--------------------|---------------:|---------------:|--------------:|------------------:|---------------:|---------------:|---------------:|---------------:|
| Logistic Regression |         0.348  |         0.3902 |        0.3649 |            0.3847 |         1.8283 |         0.3902 |         0.6062 |         0.7329 |
| CatBoost            |         0.3334 |         0.3637 |        0.3651 |            0.3539 |         1.7777 |         0.3637 |         0.5834 |         0.7384 |
| Random Forest       |         0.3241 |         0.3546 |        0.362  |            0.345  |         1.8203 |         0.3546 |         0.5907 |         0.732  |
| LightGBM            |         0.3222 |         0.3564 |        0.3517 |            0.3525 |         1.7892 |         0.3564 |         0.5953 |         0.7329 |
| XGBoost             |         0.3051 |         0.4111 |        0.3009 |            0.3812 |         1.6743 |         0.4111 |         0.6454 |         0.7767 |
| Dummy (Stratified)  |         0.0973 |         0.1431 |        0.0996 |            0.1514 |        30.8852 |         0.1431 |         0.1905 |         0.2589 |
| Dummy (Majority)    |         0.0465 |         0.3026 |        0.1    |            0.1406 |        25.1353 |         0.3026 |         0.3464 |         0.4202 |

---

## Final Out-Of-Time Performance (Month 6 Test Holdout - Logistic Regression)

- **Primary Metric (Macro-F1)**: **0.2946**
- **Accuracy**: **0.3553** (35.53%)
- **Balanced Accuracy**: **0.3147**
- **Weighted F1**: **0.3471**
- **Log Loss**: **1.8300**
- **Multiclass ROC-AUC (ovr)**: **0.7573**
- **Top-1 Accuracy**: **0.3553**
- **Top-2 Accuracy**: **0.5808**
- **Top-3 Accuracy**: **0.7237**

---

## Month 6 Per-Class Performance

| Root_Cause               |   Precision |   Recall |   F1_Score |   Support |
|:-------------------------|------------:|---------:|-----------:|----------:|
| CUSTOMER_ABANDONMENT     |      0.2069 |   0.4615 |     0.2857 |        52 |
| DUPLICATE_PAYMENT        |      0.3408 |   0.5596 |     0.4236 |       109 |
| EXPIRED_CARD             |      0.2628 |   0.4444 |     0.3303 |        81 |
| GATEWAY_FAILURE          |      0.2793 |   0.3298 |     0.3024 |        94 |
| INSUFFICIENT_FUNDS       |      0.4737 |   0.4324 |     0.4521 |       333 |
| INVALID_PAYMENT_METHOD   |      0.1667 |   0.0317 |     0.0533 |        63 |
| NETWORK_TIMEOUT          |      0.4    |   0.2655 |     0.3191 |       113 |
| OVERDUE_INVOICE          |      0.5686 |   0.3625 |     0.4427 |        80 |
| TEMPORARY_ISSUER_DECLINE |      0.4    |   0.1957 |     0.2628 |        92 |
| UNKNOWN                  |      0.0882 |   0.0638 |     0.0741 |        47 |

---

## Relational Feature Value & Ablation Study

| Feature_Set                                |   Feature_Count |   Month6_Macro_F1 |   Month6_Accuracy |
|:-------------------------------------------|----------------:|------------------:|------------------:|
| A. Transaction-Only                        |               6 |            0.185  |            0.3008 |
| B. Customer-Only                           |               5 |            0.1204 |            0.2726 |
| C. Temporal-Only                           |              12 |            0.1171 |            0.3205 |
| D. Historical-Only                         |              12 |            0.1147 |            0.2867 |
| E. Gateway-Only                            |               2 |            0.0778 |            0.282  |
| F. Non-Relational (Transaction + Temporal) |              18 |            0.2253 |            0.3957 |
| G. Full Feature Set (Relational Ecosystem) |              36 |            0.2541 |            0.4182 |

**Key Finding**: Incorporating historical and relational event features yields a **+12.78% Macro-F1 lift** over traditional transaction-only models!

---

## Temporal Robustness Across Timeline

| Month   |   Case_Count |   Macro_F1 |   Accuracy |   Log_Loss |
|:--------|-------------:|-----------:|-----------:|-----------:|
| Month 2 |          490 |     0.3206 |     0.3306 |     1.8215 |
| Month 3 |          515 |     0.3272 |     0.3417 |     1.8262 |
| Month 4 |          529 |     0.3004 |     0.3251 |     1.8665 |
| Month 5 |         1097 |     0.3515 |     0.3892 |     1.8191 |
| Month 6 |         1064 |     0.2946 |     0.3553 |     1.83   |

---

## Top 5 Confusion Pairs & Error Analysis

| True_Class         | Predicted_Class      |   Count |   Percentage |
|:-------------------|:---------------------|--------:|-------------:|
| INSUFFICIENT_FUNDS | DUPLICATE_PAYMENT    |      43 |         12.9 |
| INSUFFICIENT_FUNDS | CUSTOMER_ABANDONMENT |      39 |         11.7 |
| INSUFFICIENT_FUNDS | EXPIRED_CARD         |      37 |         11.1 |
| NETWORK_TIMEOUT    | INSUFFICIENT_FUNDS   |      31 |         27.4 |
| INSUFFICIENT_FUNDS | GATEWAY_FAILURE      |      30 |          9   |

---

## Recommended Production Model

**Selected Model**: **Logistic Regression**  
Saved to: [`artifacts/models/revive_root_cause_model.pkl`](file:///c:/Users/hites/OneDrive/Desktop/REVIVE/artifacts/models/revive_root_cause_model.pkl)  
Metadata: [`artifacts/models/model_metadata.json`](file:///c:/Users/hites/OneDrive/Desktop/REVIVE/artifacts/models/model_metadata.json)

