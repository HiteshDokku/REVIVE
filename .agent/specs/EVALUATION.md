# REVIVE Evaluation Specification

## 1. Objective

Evaluation must prove:

1. predictive accuracy
2. probability calibration
3. decision quality
4. financial benefit
5. guardrail compliance
6. failure robustness

See [ML_SPEC.md](./ML_SPEC.md) and [POLICY.md](./POLICY.md).

## 2. Baselines

Evaluate at least:

### No Action

Never intervene.

### Always Retry

Retry every retry-compatible case until the retry limit.

### Generic Reminder

Send a generic reminder to eligible cases.

### REVIVE

Risk + diagnosis + recovery propensity + economic optimization + policy.

Optional:

### RL/Contextual Bandit

Only after the baseline system is stable.

## 3. Revenue at Risk

For each active recovery case:

```text
RevenueAtRisk = unresolved amount at prediction time
```

At batch level, deduplicate underlying source objects before summing.

## 4. Gross Revenue Recovered

```text
GrossRecoveredRevenue
    = SUM(amount_recovered)
```

Only actual simulated recovery outcomes count.

## 5. Recovery Rate

```text
RecoveryRate
    = GrossRecoveredRevenue / TotalRevenueAtRisk
```

## 6. Intervention Cost

```text
TotalInterventionCost
    = SUM(cost of executed interventions)
```

Blocked actions are not charged.

## 7. Net Recovered Revenue

```text
NetRecoveredRevenue
    = GrossRecoveredRevenue - TotalInterventionCost
```

## 8. Incremental Revenue

For baseline B:

```text
IncrementalRevenue
    = REVIVE_GrossRecoveredRevenue
      - Baseline_GrossRecoveredRevenue
```

## 9. Incremental Net Revenue

```text
IncrementalNetRevenue
    = REVIVE_NetRecoveredRevenue
      - Baseline_NetRecoveredRevenue
```

## 10. Recovery Lift

```text
RecoveryLift
    = (REVIVE_RecoveryRate - Baseline_RecoveryRate)
      / Baseline_RecoveryRate
```

When baseline recovery is zero, report absolute recovery-rate difference and avoid division by zero.

## 11. Model Metrics

Risk:

- precision
- recall
- F1
- PR-AUC
- ROC-AUC
- Brier score
- calibration curve
- revenue recall

Root cause:

- accuracy
- Macro-F1
- Weighted-F1
- confusion matrix

Recovery propensity:

- ROC-AUC
- PR-AUC
- log loss
- Brier score
- calibration

## 12. Decision Metrics

### Valid Action Rate

```text
valid executed actions / all executed actions
```

### Policy Violation Rate

```text
policy-violating executions / all executions
```

Target: `0%`.

### Duplicate Action Rate

```text
duplicate executions / all executions
```

Target: `0%`.

### Stop-Rule Compliance

```text
correctly stopped workflows / workflows requiring stop
```

Target: `100%` for deterministic stop rules.

## 13. Calibration

For predicted probability bins, compare mean prediction with observed recovery frequency.

Brier score:

```text
mean((predicted_probability - actual_outcome)^2)
```

Lower is better.

## 14. Temporal Evaluation

Primary:

```text
Months 1–4 -> train
Month 5     -> validation
Month 6     -> test
```

Stress scenarios:

```text
Gateway degradation
Holiday-like behavior
New customers
High-value B2B
High failure rate
```

## 15. Stress Tests

### Gateway outage

Expected:

- retries against degraded gateway decrease
- alternate route/deferred retry increases where allowed
- retry storms do not occur

### Already-paid

Expected:

- case closes/stops
- no duplicate recovery action

### Duplicate events

Expected:

- one active recovery case
- one action per idempotency key

### LLM unavailable

Expected:

- deterministic template or escalation
- no financial policy bypass

### Model unavailable

Expected:

- conservative fallback or escalation

### Policy unavailable

Expected:

- financial action denied

### Communication opt-out

Expected:

- zero automated communication actions

## 16. Statistical Stability

Recommended evaluation seeds:

```text
42
43
44
45
46
```

Report mean, standard deviation, minimum, and maximum for major financial metrics.

Do not claim superiority from a single favorable seed.

## 17. Acceptance Targets

Initial engineering targets:

```text
Risk PR-AUC              >= 0.75
Root-cause Macro-F1      >= 0.75
Policy violations          0%
Duplicate actions          0%
Stop-rule compliance     100%
REVIVE > generic baseline on gross recovery
REVIVE > generic baseline on net recovery
```

Calibration should materially improve over an uncalibrated probability baseline.

These are synthetic-benchmark engineering targets, not real-world guarantees.

## 18. Reproducibility Metadata

Every evaluation run stores:

```text
run_id
dataset_version
dataset_hash
seed
model_versions
policy_version
scenario
configuration_hash
timestamp
```

## 19. Required Final Comparison

Every final run should produce:

| Metric | No Action | Always Retry | Generic Reminder | REVIVE |
|---|---:|---:|---:|---:|
| Revenue at Risk | computed | computed | computed | computed |
| Gross Recovered | computed | computed | computed | computed |
| Recovery Rate | computed | computed | computed | computed |
| Intervention Cost | computed | computed | computed | computed |
| Net Recovered | computed | computed | computed | computed |
| Incremental Revenue | baseline | baseline | baseline | computed |
| Policy Violations | computed | computed | computed | computed |
| Escalations | computed | computed | computed | computed |

No result may be hard-coded.
