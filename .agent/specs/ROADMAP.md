# REVIVE Implementation Roadmap

## 0. Execution Contract

This roadmap is sequential.

**Antigravity MUST implement exactly one milestone at a time.**

After every milestone it MUST:

1. Stop implementation.
2. Run relevant unit tests.
3. Run relevant integration tests.
4. Run an end-to-end/smoke test where applicable.
5. Run linting and formatting checks.
6. Run static type checking where applicable.
7. Verify every Definition of Done item.
8. Check for regressions in all previously completed P0 functionality.
9. Report files changed.
10. Report test commands and results.
11. Report failures, warnings, or blockers.
12. Report the next milestone only.
13. **WAIT FOR EXPLICIT USER INSTRUCTION BEFORE STARTING THE NEXT MILESTONE.**

If any required test fails, do not proceed.

See [AGENTS.md](./AGENTS.md).

---

# Milestone 0 — Repository Bootstrap

Priority: P0

Tasks:

- Create repository structure.
- Create `pyproject.toml`.
- Configure Ruff.
- Configure test runner.
- Configure chosen type checker.
- Add `.env.example`.
- Add application skeleton.
- Add `/health` endpoint.

Definition of Done:

- Project installs.
- Test suite starts.
- Lint passes.
- Type check passes.
- Application starts.
- `/health` returns success.

STOP after testing and reporting.

---

# Milestone 1 — Database

Priority: P0

Tasks:

- Implement SQLAlchemy models.
- Add PostgreSQL connection.
- Add Alembic.
- Implement schema from [SCHEMA.md](./SCHEMA.md).
- Add repositories.
- Add repository tests.

Definition of Done:

- Empty database migrates successfully.
- Foreign keys work.
- Monetary fields use numeric/Decimal-safe storage.
- Idempotency constraints work.
- Repository tests pass.

STOP after testing and reporting.

---

# Milestone 2 — Synthetic Revenue Environment

Priority: P0

Tasks:

- Generate customers.
- Generate subscriptions.
- Generate payments.
- Generate invoices.
- Generate interactions.
- Generate failures.
- Generate intervention outcomes.
- Implement quality checks.
- Implement reproducible seed.

Definition of Done:

- Development dataset generates successfully.
- Default-scale dataset is supported.
- All relational integrity checks pass.
- Failure types exhibit distinct behavior.
- Outcome generation is reproducible.

STOP after testing and reporting.

---

# Milestone 3 — EDA and Data Validation

Priority: P0

Tasks:

- Analyze customer distributions.
- Analyze failure distributions.
- Verify gateway effects.
- Verify recovery patterns.
- Verify intervention costs and outcomes.
- Verify labels.

Definition of Done:

- No accidental label leakage.
- Synthetic relationships are measurable and sensible.
- Temporal split is validated.

STOP after testing and reporting.

---

# Milestone 4 — Risk Model

Priority: P0

Tasks:

- Build feature pipeline.
- Build temporal split.
- Train logistic regression.
- Train random forest.
- Train XGBoost.
- Compare metrics.
- Calibrate selected model.
- Persist artifact and metadata.
- Add inference service.

Definition of Done:

- Test metrics are recorded.
- Calibration is evaluated.
- No leakage is detected.
- Inference contract works.

STOP after testing and reporting.

---

# Milestone 5 — Root Cause Model

Priority: P0

Tasks:

- Implement deterministic mappings.
- Implement ML fallback for ambiguous cases.
- Evaluate Macro-F1.
- Persist model metadata.

Definition of Done:

- Stable inference interface.
- Evaluation metrics recorded.
- Tests pass.

STOP after testing and reporting.

---

# Milestone 6 — Recovery Propensity Model

Priority: P0

Tasks:

- Construct action/outcome training records.
- Implement action-aware features.
- Train baseline classifier.
- Train XGBoost.
- Calibrate selected model.
- Evaluate temporal generalization.
- Persist artifact.

Definition of Done:

Given case + action, the model returns recovery probability, confidence, and model version.

STOP after testing and reporting.

---

# Milestone 7 — Economic Decision Engine

Priority: P0

Tasks:

- Implement candidate-action generator.
- Implement action costs.
- Implement expected recovery.
- Implement expected net recovery.
- Implement ranking.
- Implement `DecisionPolicy` interface.
- Implement `ExpectedValuePolicy`.

Definition of Done:

- Deterministic decision scenarios pass.
- Financial arithmetic is correct.
- Candidate actions are explainable.

STOP after testing and reporting.

---

# Milestone 8 — Policy and Guardrails

Priority: P0

Tasks:

- Retry limits.
- Contact limits.
- Cooldowns.
- Recovery window.
- Opt-out handling.
- High-value escalation.
- Minimum economic threshold.
- Stop rules.
- Default-deny behavior.

Definition of Done:

- Positive-path and negative-path policy tests pass.
- Policy-violation rate is zero under test scenarios.

STOP after testing and reporting.

---

# Milestone 9 — Simulator Tools

Priority: P0

Implement explicit tools for:

- get payment status
- retry payment
- schedule retry
- update payment method
- alternate gateway
- send message
- get customer history
- create escalation
- record outcome

Definition of Done:

- Tool contracts are typed.
- Idempotency works.
- Failure modes are simulated.
- Audit records are produced.

STOP after testing and reporting.

---

# Milestone 10 — LangGraph Agent

Priority: P0

Implement graph and nodes from [AGENT_SPEC.md](./AGENT_SPEC.md).

Definition of Done:

A failed payment can execute end-to-end:

```text
failure
-> case
-> risk
-> root cause
-> candidate actions
-> recovery probability
-> decision
-> policy
-> simulated action
-> outcome
-> close/retry/escalate
```

STOP after testing and reporting.

---

# Milestone 11 — Financial Evaluation

Priority: P0

Implement:

- No Action baseline
- Always Retry baseline
- Generic Reminder baseline
- REVIVE strategy
- financial metrics
- model metrics
- safety metrics
- multi-seed run metadata

Definition of Done:

A reproducible command produces a complete comparison report.

STOP after testing and reporting.

---

# Milestone 12 — Control Tower UI

Priority: P1

Implement pages from [UI_SPEC.md](./UI_SPEC.md).

Definition of Done:

A judge can understand:

- revenue at risk
- recovery performance
- selected actions
- decision reasoning
- audit history
- model performance

without inspecting source code.

STOP after testing and reporting.

---

# Milestone 13 — Fault Injection and Failure Recovery

Priority: P1

Implement and test:

- gateway outage
- duplicate events
- already-paid state
- LLM unavailable
- model unavailable
- policy unavailable
- customer opt-out
- API timeout

Definition of Done:

Every fault path has deterministic safe behavior and an audit record.

STOP after testing and reporting.

---

# Milestone 14 — Advanced Differentiators

Priority: P2

Only begin after MVP is stable.

Potential order:

1. Promise-to-pay
2. Hinglish communication
3. Checkout abandonment
4. B2B receivables
5. Gateway leakage detection
6. Recovery memory

STOP after each separately implemented feature group if broken into sub-milestones.

---

# Milestone 15 — RL / Contextual Bandit Experiment

Priority: P3

Only begin after:

- simulator stable
- baselines stable
- financial evaluation stable
- recovery model stable
- decision-policy interface stable

Compare:

```text
ExpectedValuePolicy
vs
ContextualBandit/RLPolicy
```

Retain RL only if it improves held-out financial outcomes without degrading safety or interpretability.

STOP after evaluation and reporting.

---

# Milestone 16 — Final Validation

Priority: P0

Run all major scenarios:

```text
NORMAL
GATEWAY_DEGRADATION
HOLIDAY
HIGH_VALUE_B2B
NEW_CUSTOMERS
API_FAILURE
LLM_FAILURE
ALREADY_PAID
DUPLICATE_EVENT
OPT_OUT
```

Definition of Done:

- Accuracy measured.
- Calibration measured.
- Revenue recovered measured.
- Incremental revenue measured.
- Policy violations = 0.
- Stop-rule compliance = 100%.
- Failure recovery demonstrated.

STOP after testing and reporting.

---

# Milestone 17 — Demo and Submission Polish

Priority: P1

Final sequence:

1. Show revenue at risk.
2. Run baselines.
3. Run REVIVE.
4. Show incremental revenue.
5. Inspect one decision trace.
6. Inject a failure.
7. Show safe adaptation.
8. Show audit trail.
9. Show final recovered revenue.

No hard-coded business metrics.

STOP after final validation and report the submission-ready state.

---

## Global Roadmap Rule

**NEVER IMPLEMENT MULTIPLE MILESTONES IN A SINGLE AUTONOMOUS TURN.**

After each milestone:

```text
Implement
-> Test Everything Relevant
-> Validate Definition of Done
-> Report Results
-> STOP
-> Wait for Explicit User Instruction
```
