# Instructions for Google Antigravity

## 1. Role

You are implementing REVIVE, an autonomous revenue-recovery system.

Treat the specification pack as the source of truth.

Before modifying code, determine which specification files apply to the current task.

Primary references:

- [PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md)
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

---

## 2. NON-NEGOTIABLE EXECUTION RULE: ONE MILESTONE AT A TIME

This is the most important instruction in the entire specification pack.

You MUST implement exactly one milestone at a time from [ROADMAP.md](./ROADMAP.md).

After finishing that milestone, you MUST STOP.

Do NOT automatically continue to the next milestone.

Before stopping, you MUST:

1. Run all relevant unit tests.
2. Run all relevant integration tests.
3. Run end-to-end tests when applicable.
4. Run the configured linter.
5. Run the configured formatter/check.
6. Run static type checking when applicable.
7. Execute the milestone-specific smoke test.
8. Verify every Definition of Done item in [ROADMAP.md](./ROADMAP.md).
9. Verify that no P0 regression was introduced.
10. Report changed files.
11. Report commands run and their results.
12. Report unresolved warnings/errors.
13. Report the exact next milestone, but DO NOT implement it.
14. Wait for explicit user instruction before continuing.

If tests fail, DO NOT proceed to the next milestone. Fix or clearly report the failure and stop.

If a requirement is ambiguous, inspect the relevant specification files and repository state first. Do not silently invent a conflicting architecture.

---

## 3. Primary Objective

Build a reliable end-to-end system that demonstrates:

```text
Accurate detection
+
Accurate diagnosis
+
Calibrated recovery prediction
+
Economic action selection
+
Deterministic guardrails
+
Bounded agentic execution
+
Actual simulated recovery
+
Auditability
```

Do not optimize for complexity.

Optimize for:

```text
Correctness
Reproducibility
Explainability
Testability
Financial usefulness
```

---

## 4. Technology Stack

### Language

Python 3.12

### Backend

FastAPI

### Validation

Pydantic v2

### Database

PostgreSQL
SQLAlchemy 2.x
Alembic

### Machine Learning

Pandas
NumPy
Scikit-learn
XGBoost
LightGBM only when justified

### Agent

LangGraph
LangChain only where useful

### LLM

Use an abstraction around the configured provider.

Do not hard-code provider-specific calls throughout the application.

### Frontend

Streamlit

### Visualization

Plotly

### Testing

Pytest

### Formatting and linting

Ruff

### Static typing

Use either Pyright or MyPy consistently across the project.

### Configuration

YAML + environment variables

### Packaging

pyproject.toml

### Optional packaging/deployment

Docker / Docker Compose when useful.

Do not add Redis, Kafka, Kubernetes, Celery, vector databases, or service meshes without a concrete requirement.

---

## 5. Required Folder Structure

Use:

```text
revive/
├── README.md
├── pyproject.toml
├── .env.example
├── docker-compose.yml
│
├── .agent/
│   └── specs/
│       ├── PROJECT_OVERVIEW.md
│       ├── ARCHITECTURE.md
│       ├── TECHNICAL_SPEC.md
│       ├── SCHEMA.md
│       ├── DATA_GENERATION.md
│       ├── ML_SPEC.md
│       ├── AGENT_SPEC.md
│       ├── POLICY.md
│       ├── EVALUATION.md
│       ├── UI_SPEC.md
│       ├── ROADMAP.md
│       └── AGENTS.md
│
├── config/
│   ├── settings.yaml
│   ├── thresholds.yaml
│   └── intervention_policies.yaml
│
├── data/
│   ├── raw/
│   ├── processed/
│   ├── synthetic/
│   └── predictions/
│
├── notebooks/
├── src/
│   ├── data/
│   ├── features/
│   ├── models/
│   ├── decision/
│   ├── policy/
│   ├── agent/
│   │   ├── nodes/
│   │   └── tools/
│   ├── simulator/
│   ├── database/
│   ├── audit/
│   └── api/
├── frontend/
│   ├── app.py
│   ├── pages/
│   └── components/
├── tests/
├── scripts/
└── artifacts/
    ├── models/
    └── evaluations/
```

---

## 6. Coding Principles

- Keep modules small and responsibility-focused.
- Use explicit input/output contracts.
- Use Pydantic at API boundaries.
- Keep UI code separate from business logic.
- Keep financial arithmetic deterministic.
- Use Decimal or database NUMERIC for authoritative monetary values.
- Store timestamps in UTC.
- Use correlation IDs for recovery workflows.
- Avoid hidden side effects.
- Make external operations explicit.

---

## 7. Naming Conventions

Python functions and variables: `snake_case`

Classes: `PascalCase`

Constants: `UPPER_SNAKE_CASE`

Database objects: `snake_case`

Use consistent naming throughout the repository.

---

## 8. Testing Requirements

Every important component must have tests.

Minimum coverage areas:

```text
Database repositories
Synthetic generators
Feature pipeline
Risk model inference
Root-cause inference
Recovery inference
Decision engine
Policy engine
Agent graph
Simulator tools
Audit logging
Financial metrics
```

Critical safety rules require explicit negative tests.

Examples:

```text
retry_count == maximum
=> retry action blocked

communication_opt_out == true
=> communication blocked

payment_status == PAID
=> recovery stops
```

---

## 9. Mandatory Test Cycle After Every Milestone

At the end of EVERY milestone:

```text
Implement
  -> Unit Tests
  -> Integration Tests
  -> E2E/Smoke Test
  -> Lint
  -> Type Check
  -> Definition-of-Done Verification
  -> Report
  -> STOP
```

Do not merge incomplete work into the next milestone.

Do not skip tests because the change appears small.

---

## 10. Financial Safety

The agent must never:

- Change payment amounts without an authorized tool.
- Mark arbitrary transactions as successful.
- Ignore policy results.
- Retry indefinitely.
- Contact opted-out customers.
- Perform autonomous high-value actions when human approval is required.
- Treat timeouts as confirmed payment failures.
- Execute a mutation without idempotency.

See [POLICY.md](./POLICY.md).

---

## 11. LLM Rules

Use an LLM only where it adds clear value.

Appropriate:

- Customer-language understanding
- Promise-to-pay extraction
- Message generation
- Case summarization
- Natural-language explanations

Do NOT use an LLM as the authoritative source for:

- Payment state
- Money arithmetic
- Retry counts
- Policy thresholds
- Authorization
- Amount recovered
- Case lifecycle state

All structured LLM outputs that influence application logic must be validated with Pydantic.

---

## 12. ML Rules

For structured data, start with:

- Logistic Regression
- Random Forest
- XGBoost

Do not use deep learning simply because the project contains AI.

Do not train on future information.

Do not expose the held-out test set to model-selection decisions.

See [ML_SPEC.md](./ML_SPEC.md).

---

## 13. RL Rules

Do NOT make RL the initial architecture.

The first decision policy is:

```text
ExpectedValuePolicy
```

The decision interface must allow future replacement by:

```text
ContextualBanditPolicy
RLPolicy
```

RL may be implemented only after:

- The simulator is stable.
- Baselines are stable.
- Financial evaluation is stable.
- Recovery propensity works.
- The decision interface is isolated.

RL is optional and must only be retained if it demonstrates measurable improvement on held-out scenarios.

---

## 14. Database Rules

- All schema changes use Alembic.
- Monetary values use NUMERIC/Decimal.
- Foreign keys must be enforced.
- Audit events are append-only through the application.
- Idempotency protects mutating actions.
- Closed cases cannot receive new interventions.

---

## 15. API Rules

All APIs use `/api/v1`.

Responses must use predictable Pydantic schemas.

Never expose raw stack traces to end users.

Error responses should contain an error code, human-readable message, and correlation ID when applicable.

---

## 16. Configuration Rules

Do not hard-code:

- Retry limits
- Contact limits
- Financial thresholds
- Intervention costs
- Model paths
- Credentials
- Database credentials

Use YAML for non-secret operational configuration and environment variables for secrets.

---

## 17. Security Rules

Never commit:

```text
.env
API keys
Passwords
Tokens
Private keys
Production credentials
```

Only `.env.example` may be committed.

No real payment credentials are needed for this project.

---

## 18. Performance Rules

Do not prematurely optimize.

Correctness comes first.

Introduce caching, background jobs, async processing, or parallel inference only when an actual measured requirement exists.

---

## 19. Observability

Each recovery workflow should retain:

```text
run_id
case_id
customer_id
correlation_id
model versions
policy version
selected action
execution result
outcome
```

These must be visible through the audit system.

---

## 20. UI Rules

The UI must show real backend state.

Never hard-code recovered revenue, case counts, model metrics, or policy violations.

Demo mode may use deterministic synthetic data but must execute the real workflow/evaluation pipeline.

See [UI_SPEC.md](./UI_SPEC.md).

---

## 21. Dependency Rules

Before adding a dependency, answer:

1. What concrete problem does it solve?
2. Why is the current stack insufficient?
3. What complexity does it introduce?
4. Is it required for MVP?

Avoid dependency creep.

---

## 22. Definition of Done for Any Feature

A feature is complete only when:

- Implementation exists.
- Relevant tests exist.
- Relevant integration behavior is tested.
- Errors are handled.
- Logging exists where appropriate.
- Documentation is updated.
- The feature conforms to the specification pack.
- Existing P0 behavior remains green.

---

## 23. What NOT to Over-Engineer

Do not introduce merely for architectural appearance:

```text
Microservices
Kubernetes
Kafka
Redis
Vector databases
Multi-agent swarms
Custom neural networks
RL from day one
Real payment integrations
Complex MLOps infrastructure
```

---

## 24. Earliest Required Vertical Slice

Build this before spending substantial effort on UI polish or advanced AI:

```text
Synthetic failed payment
    ->
Recovery case
    ->
Risk model
    ->
Root cause
    ->
Recovery prediction
    ->
Expected-value decision
    ->
Policy
    ->
Simulated retry
    ->
Payment recovery
    ->
Audit event
    ->
₹ recovered metric
```

---

## 25. Final Operating Rule

When in doubt:

```text
STOP
or
ESCALATE
```

The goal is not the largest codebase.

The goal is a trustworthy, measurable revenue-recovery system that demonstrates accurate AI, economic decision-making, bounded autonomy, failure recovery, auditability, and incremental recovered revenue.

After every milestone, TEST EVERYTHING RELEVANT, verify the Definition of Done, REPORT RESULTS, and STOP until explicitly instructed to continue.
