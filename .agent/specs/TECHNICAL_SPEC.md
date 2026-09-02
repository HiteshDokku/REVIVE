# REVIVE Technical Specification

## 1. Stack
Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, PostgreSQL, Pandas, NumPy, scikit-learn, XGBoost, LangGraph, optional LangChain, Streamlit, Plotly, Pytest, Ruff, Pyright or MyPy.

See [AGENTS.md](./AGENTS.md).

## 2. Canonical Revenue Event

```python
class RevenueEvent(BaseModel):
    event_id: str
    event_type: str
    occurred_at: datetime
    customer_id: str
    source_id: str
    amount: Decimal | None = None
    currency: str = "INR"
    metadata: dict[str, Any] = Field(default_factory=dict)
```

Supported events: `PAYMENT_FAILED`, `PAYMENT_SUCCEEDED`, `PAYMENT_RETRY_FAILED`, `CHECKOUT_ABANDONED`, `SUBSCRIPTION_RENEWAL_FAILED`, `INVOICE_OVERDUE`, `CUSTOMER_RESPONSE`, `PAYMENT_STATUS_CHANGED`.

## 3. Model Contracts

```python
class RiskAssessmentService:
    def assess(self, event: RevenueEvent) -> RiskAssessment: ...


class RootCauseService:
    def diagnose(self, event: RevenueEvent, context: dict) -> RootCauseResult: ...


class RecoveryPredictionService:
    def predict(self, case: RecoveryCaseContext, action: CandidateAction) -> RecoveryPrediction: ...


class DecisionPolicy(Protocol):
    def choose_action(
        self, state: RecoveryDecisionContext, candidates: list[CandidateActionScore]
    ) -> DecisionResult: ...
```

All model outputs include probability/confidence, model name, model version and inference timestamp where applicable.

## 4. Candidate Actions
Candidate generation is deterministic and root-cause aware.

`TEMPORARY_ISSUER_DECLINE`: `RETRY_NOW`, `RETRY_LATER`, reminder.

`INSUFFICIENT_FUNDS`: delayed retry, reminder.

`EXPIRED_CARD`: payment-method update, reminder.

`GATEWAY_FAILURE`: defer retry, alternate gateway.

`CHECKOUT_ABANDONMENT`: payment link, reminder.

`OVERDUE_INVOICE`: reminder, promise-to-pay, finance escalation.

Invalid actions must be excluded before recovery scoring.

## 5. Economic Decision

```text
ExpectedRecovery(action) = P(recovery | state, action) * amount_at_risk
ExpectedNetRecovery(action) = ExpectedRecovery(action) - intervention_cost(action)
```

The initial `ExpectedValuePolicy` chooses the highest eligible expected-net-recovery action. Tie-breaking is deterministic: higher confidence, higher amount at risk, older case.

## 6. Core APIs

### Health
`GET /health`

### Create Case
`POST /api/v1/recovery/cases`

```json
{"source_type":"PAYMENT","source_id":"pay_001","customer_id":"cust_001"}
```

### Get Case
`GET /api/v1/recovery/cases/{case_id}`

### List Cases
`GET /api/v1/recovery/cases?status=&source_type=&min_amount=&max_amount=&min_risk=&limit=&offset=`

### Recommendation
`POST /api/v1/recovery/cases/{case_id}/recommendation`

### Policy Check
`POST /api/v1/policy/check`

```json
{"case_id":"case_001","action":"RETRY_LATER"}
```

### Run Workflow
`POST /api/v1/recovery/cases/{case_id}/run`

```json
{"mode":"AUTONOMOUS"}
```

Modes: `AUTONOMOUS`, `DRY_RUN`, `HUMAN_APPROVAL`.

### Simulation Generation
`POST /api/v1/simulation/generate`

```json
{"customers":5000,"months":6,"seed":42}
```

### Simulation Run
`POST /api/v1/simulation/run`

```json
{"strategy":"REVIVE","scenario":"NORMAL","seed":42}
```

Strategies: `NO_ACTION`, `ALWAYS_RETRY`, `GENERIC_REMINDER`, `REVIVE`; optional `RL_POLICY` only after implementation.

### Fault Injection
`POST /api/v1/simulation/fault`

```json
{"fault_type":"GATEWAY_OUTAGE","gateway":"gateway_a","severity":0.8,"duration_minutes":60}
```

## 7. Tool Contracts

Payment tools:
- `get_payment_status(payment_id)`
- `retry_payment(payment_id, idempotency_key)`
- `schedule_retry(payment_id, execute_at, idempotency_key)`
- `update_payment_method(payment_id, idempotency_key)`
- `use_alternate_gateway(payment_id, gateway, idempotency_key)`

Communication tools:
- `send_message(customer_id, channel, message, idempotency_key)`

Customer/invoice tools:
- `get_customer_history(customer_id)`
- `get_invoice_status(invoice_id)`
- `send_invoice_reminder(invoice_id, ...)`
- `create_escalation(case_id, reason)`

Audit tools:
- `record_audit_event(...)`
- `record_outcome(...)`

## 8. Idempotency
All mutating operations use:

`{case_id}:{action_type}:{attempt_number}`

Repeated execution with the same key returns the prior result and does not create duplicate side effects.

## 9. Case State Machine

`CREATED -> ANALYZING -> ACTION_PENDING -> EXECUTING -> WAITING/ACTION_PENDING/RECOVERED/EXHAUSTED/ESCALATED -> CLOSED`

Terminal states: `CLOSED`, `CANCELLED` after final state recording. A closed case cannot receive new interventions.

## 10. Error Handling
- Tool timeout: verify authoritative state before retry.
- Unknown execution result: do not assume failure; query status or escalate.
- LLM error: deterministic template or escalation.
- Model error: conservative fallback or escalation.
- Policy error: deny financial action.
- DB error: do not execute new financial mutations.

## 11. Vertical Slice
The earliest end-to-end test must execute:

`Failed Payment -> Case -> Risk -> Root Cause -> Candidate Actions -> Recovery Prediction -> Decision -> Policy -> Simulated Retry -> Outcome -> Audit -> Case Close`

See [ROADMAP.md](./ROADMAP.md).
