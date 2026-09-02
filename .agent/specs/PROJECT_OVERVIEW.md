# REVIVE — Autonomous Revenue Recovery & Intervention Engine

## 1. Purpose

REVIVE is an autonomous, confidence-aware revenue-recovery platform that detects revenue at risk, diagnoses the cause, predicts the expected recovery value of candidate interventions, selects the economically optimal permitted action, executes a bounded workflow, measures the actual financial outcome, and records a complete audit trail.

Primary revenue-loss scenarios:

1. Failed payments
2. Subscription renewal failures
3. Checkout abandonment
4. Overdue B2B receivables
5. Payment infrastructure degradation

The deepest MVP implementation should focus on failed-payment and subscription recovery while keeping the common recovery-case architecture extensible.

See [ARCHITECTURE.md](./ARCHITECTURE.md) and [TECHNICAL_SPEC.md](./TECHNICAL_SPEC.md).

## 2. Core Loop

```text
Detection -> Diagnosis -> Prediction -> Decision -> Policy Check -> Action -> Outcome -> Measurement -> Audit
```

REVIVE must not stop at identifying risk. The primary objective is measurable incremental revenue recovery while preventing unsafe, unnecessary, duplicate, or non-compliant actions.

## 3. User Value

A merchant/revenue-operations user should be able to answer:

> How much revenue is at risk, why is it at risk, what should we do, why should we do it, what did REVIVE actually do, and how much money did it recover?

The control tower must expose:

- Revenue at risk
- Expected recoverable revenue
- Ranked recovery opportunities
- Candidate interventions
- Model confidence
- Policy outcome
- Actual recovery
- Baseline comparison
- Audit trail
- Failure-recovery behavior

See [UI_SPEC.md](./UI_SPEC.md).

## 4. Differentiation

REVIVE is intentionally more than a payment retry agent.

The system combines:

```text
Accurate ML prediction
+
Root-cause diagnosis
+
Action-level recovery prediction
+
Expected monetary value optimization
+
Deterministic guardrails
+
Bounded LangGraph orchestration
+
Failure injection and recovery
+
Actual incremental ₹ measurement
+
Decision auditability
```

## 5. AI Judgment Principle

Use the right tool for the right task:

| Task | Preferred technology |
|---|---|
| Structured risk prediction | XGBoost/LightGBM |
| Root-cause classification | Rules + ML |
| Recovery probability | Calibrated ML |
| Action optimization | Deterministic economic optimizer |
| Policy enforcement | Deterministic rules |
| Workflow orchestration | LangGraph |
| Customer response interpretation | LLM |
| Message generation | LLM + templates |
| Financial arithmetic | Deterministic Python/Decimal |

LLMs must never become the source of truth for payment state, money, authorization, or policy.

See [ML_SPEC.md](./ML_SPEC.md), [AGENT_SPEC.md](./AGENT_SPEC.md), and [POLICY.md](./POLICY.md).

## 6. Primary Success Metrics

### Financial

- Revenue at Risk
- Gross Revenue Recovered
- Net Revenue Recovered
- Recovery Rate
- Baseline Recovery
- Incremental Revenue
- Incremental Net Revenue

### ML

- PR-AUC
- Precision
- Recall
- F1
- Root-cause Macro-F1
- Calibration
- Brier score

### Agent/Safety

- Policy-violation rate
- Duplicate-action rate
- Stop-rule compliance
- Valid-action rate
- Escalation rate

See [EVALUATION.md](./EVALUATION.md).

## 7. MVP Scope

Mandatory:

1. Synthetic merchant environment
2. Customer, payment, subscription, invoice, interaction, and recovery data
3. Risk model
4. Root-cause engine
5. Recovery-propensity model
6. Economic decision engine
7. Policy engine
8. LangGraph workflow
9. Payment/customer simulator
10. Audit trail
11. Baseline strategies
12. Financial evaluation
13. Streamlit control tower

Advanced features should only be added after the MVP is stable:

- B2B receivables workflow
- Checkout-abandonment workflow
- Hinglish recovery
- Promise-to-pay
- Gateway degradation detection
- Recovery memory
- Contextual bandit/RL experiment

See [ROADMAP.md](./ROADMAP.md).

## 8. Non-Goals

Do not build initially:

- Real payment-network integrations
- Real-money movement
- Production customer data integrations
- RL as the first decision engine
- Unrestricted autonomous financial actions
- Unnecessary distributed infrastructure
- A multi-agent swarm without a concrete need

## 9. Primary Demo Outcome

The final system should process a reproducible synthetic batch and show actual computed numbers, for example:

```text
Revenue at Risk       ₹X
Baseline Recovered    ₹Y
REVIVE Recovered      ₹Z
Incremental Revenue   ₹(Z-Y)
Policy Violations     0
```

The actual values must always come from the simulator/evaluation pipeline.

## 10. Specification Graph

Use these documents together:

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [TECHNICAL_SPEC.md](./TECHNICAL_SPEC.md)
- [SCHEMA.md](./SCHEMA.md)
- [DATA_GENERATION.md](./DATA_GENERATION.md)
- [ML_SPEC.md](./ML_SPEC.md)
- [AGENT_SPEC.md](./AGENT_SPEC.md)
- [POLICY.md](./POLICY.md)
- [EVALUATION.md](./EVALUATION.md)
- [UI_SPEC.md](./UI_SPEC.md)
- [ROADMAP.md](./ROADMAP.md)
- [AGENTS.md](./AGENTS.md)
