# REVIVE Machine Learning Specification

## 1. Strategy

REVIVE uses ML for quantitative prediction and LLMs only for appropriate unstructured-language tasks.

Initial structured-model candidates:

- Logistic Regression
- Random Forest
- XGBoost
- LightGBM only when justified by measured benefit

Do not introduce deep learning without demonstrated validation benefit.

## 2. Model Inventory

Primary models:

1. Revenue Risk Model
2. Root-Cause Model
3. Recovery Propensity Model

Optional:

4. Gateway/Revenue Leakage Anomaly Detector

See [DATA_GENERATION.md](./DATA_GENERATION.md).

## 3. Revenue Risk Model

### Target

```text
P(revenue is recoverably at risk)
```

### Features

Transaction:

- amount
- payment method
- gateway
- failure code
- failure reason
- hour
- weekday
- day-of-month

Customer:

- historical payment success rate
- failure count
- average payment delay
- lifetime value
- customer age
- active subscriptions

History:

- failures in last 7/30 days
- retries in last 30 days
- prior recovery rate

Context:

- recent gateway failure rate
- current retry count
- time since failure
- intervention count

### Model comparison

Train at least:

```text
Majority baseline
Logistic Regression
Random Forest
XGBoost
```

Select based on PR-AUC, revenue recall, calibration, and business usefulness, not raw accuracy alone.

## 4. Root-Cause Model

Classes:

```text
TEMPORARY_ISSUER_DECLINE
INSUFFICIENT_FUNDS
EXPIRED_CARD
INVALID_PAYMENT_METHOD
GATEWAY_FAILURE
NETWORK_TIMEOUT
CUSTOMER_ABANDONMENT
DUPLICATE_PAYMENT
OVERDUE_INVOICE
UNKNOWN
```

Use deterministic mapping for directly known provider codes before ML classification where appropriate.

Metrics:

- accuracy
- Macro-F1
- Weighted-F1
- per-class precision/recall
- confusion matrix

Macro-F1 is primary.

## 5. Recovery Propensity Model

Target:

```text
P(recovery | current state, candidate action)
```

The action must be included as a model feature.

Features:

- customer features
- transaction features
- root cause
- action type
- amount
- retry count
- elapsed time
- communications
- gateway state
- customer response history

Start with Logistic Regression and XGBoost.

## 6. Probability Calibration

Recovery probabilities feed directly into money calculations and must therefore be calibrated.

Evaluate:

- reliability diagrams
- Brier score
- calibration error

Candidate calibrators:

- Platt scaling
- isotonic regression

Calibration must be fit without touching the held-out test set.

## 7. Feature Leakage Rules

Prediction-time features must never include future:

- intervention outcomes
- payment success state
- customer response
- retry count
- amount recovered
- future events

History features may only use records available before prediction time.

## 8. Train/Validation/Test Strategy

Primary split:

```text
Months 1–4 -> train
Month 5     -> validation
Month 6     -> test
```

Additional stress sets:

```text
Gateway degradation
Holiday-like behavior
New-customer cohort
High-value B2B cohort
```

## 9. Required Metrics

Risk:

- Precision
- Recall
- F1
- PR-AUC
- ROC-AUC
- Brier score
- Calibration
- Revenue Recall

Root cause:

- Accuracy
- Macro-F1
- Weighted-F1

Recovery propensity:

- ROC-AUC
- PR-AUC
- Log loss
- Brier score
- Calibration

## 10. Revenue Recall

```text
Revenue Recall
=
Recoverable revenue correctly identified
/
Total truly recoverable revenue
```

This prevents a model from appearing strong while missing high-value cases.

## 11. Model Metadata

Every model artifact must store:

```text
model_name
model_version
training_timestamp
training_dataset_hash
feature_schema_version
metrics
artifact_uri
```

See [SCHEMA.md](./SCHEMA.md).

## 12. Inference Contract

Every inference must expose:

```json
{
  "prediction": 0.84,
  "confidence": 0.81,
  "model_name": "recovery_propensity",
  "model_version": "1.0.0"
}
```

## 13. Optional Anomaly Detector

Monitor gateway/segment failure rates using time-window features.

Output should include:

```text
anomaly_score
cluster_type
affected_gateway
window_start
window_end
```

This is secondary to the MVP.

## 14. RL Readiness

The model layer must not depend on the decision algorithm. Recovery probabilities remain inputs to the initial ExpectedValuePolicy and future contextual-bandit/RL policies.

See [ROADMAP.md](./ROADMAP.md).
