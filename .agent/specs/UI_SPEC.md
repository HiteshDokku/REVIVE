# REVIVE UI Specification

## 1. Technology

Use Streamlit as the initial operator/control-tower frontend.

UI code must call backend/application services and must not contain core recovery/business logic.

See [TECHNICAL_SPEC.md](./TECHNICAL_SPEC.md).

## 2. Navigation

Primary routes/pages:

```text
Control Tower
Recovery Cases
Decision Trace
Simulation Lab
Audit Explorer
Model Performance
```

## 3. Control Tower

Route:

```text
/
```

Header:

```text
REVIVE
Autonomous Revenue Recovery & Intervention Engine
```

Primary actions:

```text
Run Recovery
Run Simulation
Inject Fault
Refresh
```

## 4. KPI Cards

Show:

1. Revenue at Risk
2. Expected Recovery
3. Recovered Revenue
4. Incremental Revenue
5. Active Recovery Cases
6. Policy Blocks

All values must be computed from backend state.

## 5. Revenue Funnel

Display:

```text
Revenue Events
  -> Revenue at Risk
  -> Actionable Cases
  -> Approved Interventions
  -> Successful Recoveries
```

## 6. Recovery Charts

Required visualizations:

- Revenue recovered by strategy
- Recovery rate over time
- Revenue at risk by source type
- Recovery by intervention type
- Risk distribution by count and monetary value

## 7. Top Opportunities Table

Columns:

```text
Priority
Case ID
Customer
Amount at Risk
Risk
Root Cause
Recommended Action
Expected Recovery
Confidence
Policy
Status
```

Sort primarily by expected net recovery.

## 8. Case Detail

Sections:

### Summary

Case ID, customer, source, amount, status.

### Risk

Probability, model version, important feature context.

### Root Cause

Cause, confidence, evidence.

### Candidate Actions

For every candidate:

```text
Action
Recovery Probability
Expected Recovery
Cost
Expected Net Recovery
Eligibility
```

### Final Decision

Show:

```text
Selected Action
Expected Recovery
Expected Net Recovery
Confidence
Policy Result
```

## 9. Decision Trace

Timeline should expose events such as:

```text
Payment failure detected
Risk assessed
Root cause identified
Candidate actions generated
Recovery probabilities calculated
Action selected
Policy checked
Action executed
Outcome observed
Case closed/stopped
```

Each event should have an expandable structured detail view.

## 10. Explainability

The user should be able to inspect:

```text
Why was this case flagged?
Why this root cause?
What alternatives were considered?
Why was this action selected?
What was expected to be recovered?
What did the policy allow?
What actually happened?
```

Explanations must come from stored decision information and not contradict it.

## 11. Simulation Lab

Route:

```text
/simulation
```

Controls:

```text
customer count
months
scenario
seed
strategy
fault mode
```

Scenarios:

```text
NORMAL
GATEWAY_DEGRADATION
HOLIDAY
HIGH_VALUE_B2B
NEW_CUSTOMERS
```

Strategies:

```text
NO_ACTION
ALWAYS_RETRY
GENERIC_REMINDER
REVIVE
```

## 12. Simulation Comparison

Show side-by-side strategy results for:

- Revenue at risk
- Gross recovered
- Recovery rate
- Intervention cost
- Net recovered
- Policy violations
- Escalations

## 13. Fault Injection

Support:

```text
GATEWAY_OUTAGE
PAYMENT_API_TIMEOUT
DUPLICATE_EVENTS
ALREADY_PAID
LLM_UNAVAILABLE
MODEL_UNAVAILABLE
POLICY_UNAVAILABLE
```

Show:

```text
Fault
Expected System Response
Actual System Response
Outcome
```

## 14. Audit Explorer

Route:

```text
/audit
```

Filters:

```text
case ID
event type
action type
actor
date
policy result
```

Display complete audit event timeline.

## 15. Model Performance

Route:

```text
/models
```

Show:

Risk:

- PR-AUC
- Precision
- Recall
- F1
- Brier score
- calibration chart

Root cause:

- Macro-F1
- confusion matrix

Recovery:

- PR-AUC
- Brier score
- calibration chart

Show model versions and evaluation run IDs.

## 16. Responsive Behavior

Desktop-first.

Wide desktop: 4–6 KPI cards in one row.

Medium: wrap cards.

Narrow: stack cards and horizontally scroll data tables rather than truncate financial fields.

## 17. Status Representation

Use both label and visual signal.

```text
Recovered -> positive
Pending -> warning
Blocked/Failed -> negative
In Progress -> informational
Closed -> neutral
```

Do not rely on color alone.

## 18. Empty States

Every page must provide a useful empty state.

Examples:

```text
No active revenue-risk cases.
No interventions have been executed.
No policy violations detected.
No simulations have been run yet.
```

## 19. Error States

Display:

- human-readable summary
- correlation ID
- safe retry option where applicable
- audit reference where applicable

Never expose raw stack traces.

## 20. Demo Mode

Provide deterministic controls for:

```text
Run baselines
Run REVIVE
Inject gateway failure
Open highest-value case
Show decision trace
Show final recovered revenue
```

Demo mode must invoke real backend logic and real evaluation calculations.
