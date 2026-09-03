# Milestone 13 — Fault Injection and Failure Recovery Validation Report

## A. Files Created
- `src/faults/__init__.py`: Package init.
- `src/faults/models.py`: Defines the `FaultType` enum and `SimulatedFaultError` schema.
- `src/faults/injector.py`: Defines the deterministic `FaultInjector` singleton.
- `tests/test_fault_injection.py`: Comprehensive test suite for all 8 fault scenarios.

## B. Files Modified
- `src/agent/nodes/risk.py`: Intercepted `MODEL_UNAVAILABLE` to fallback to safe default (50% risk).
- `src/agent/nodes/root_cause.py`: Intercepted `MODEL_UNAVAILABLE` and `LLM_UNAVAILABLE` to return safe default ("UNKNOWN" root cause).
- `src/agent/nodes/propensity.py`: Intercepted `MODEL_UNAVAILABLE` to fallback to safe default prediction.
- `src/agent/nodes/policy.py`: Intercepted `POLICY_UNAVAILABLE` to trigger DEFAULT DENY.
- `src/agent/tools/payment.py`: Intercepted `GATEWAY_OUTAGE` (retryable), `API_TIMEOUT` (retryable), and `ALREADY_PAID` (terminal blocked).
- `src/agent/tools/communication.py`: Intercepted `API_TIMEOUT` to fail gracefully.
- `src/agent/tools/base.py`: Intercepted `DUPLICATE_EVENT` to explicitly raise `DuplicateExecutionError`.
- `src/policy/guardrails.py`: Enforced `CUSTOMER_OPT_OUT` properly in the policy engine.
- `frontend/app.py`: Wired the "Inject Fault" and "Clear Faults" UI buttons to the backend `FaultInjector`.

## C. Fault Matrix

| Fault | Injection Point | System Response | Agent Routing | Audit Result | Test |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **GATEWAY_OUTAGE** | Payment Tool | Execution fails, returns success=False | Retryable outcome | Failed outcome created | `test_gateway_outage` |
| **API_TIMEOUT** | Payment/Comm Tool | Execution fails | Uncertain/retryable | Failed outcome created | `test_api_timeout_*` |
| **DUPLICATE_EVENT** | Idempotency Check | Raises DuplicateExecutionError | Safely stops tool | Audit/ToolResult handles it | `test_duplicate_event` |
| **ALREADY_PAID** | Payment Tool | Tool blocks execution | Terminal failure | Failed tool result | `test_already_paid` |
| **LLM_UNAVAILABLE** | Root Cause Node | Safe fallback to "UNKNOWN" | Routes normally | Audit with LLM info | `test_model_unavailable_*` |
| **MODEL_UNAVAILABLE**| Risk/Prop/Root Nodes| Safe default fallback prediction | Routes safely | Audit captures fallback | `test_model_unavailable_*` |
| **POLICY_UNAVAILABLE**| Policy Check Node | Safe DENY fallback | Stops/Escalates | Audit captures DENY | `test_policy_unavailable_*` |
| **CUSTOMER_OPT_OUT** | Guardrails Engine | Communication DENIED | Safely blocks tool | Audit captures DENY | `test_customer_opt_out` |

## D. Testing
- M13 Fault specific tests: `pytest tests/test_fault_injection.py -v` (8 passed in 5.69s)
- Full Regression: `pytest tests/ -v` (127 passed, 148 warnings in 71.43s)
- Formatting: `ruff check --fix .` and `ruff format .` complete.
- Typing: `mypy src scripts tests --ignore-missing-imports` (Success)

## E. Regression Status
- M0: PASS
- M1: PASS
- M2: PASS
- M3: PASS
- M4: PASS
- M5: PASS
- M6: PASS
- M7: PASS
- M8: PASS
- M9: PASS
- M10: PASS
- M11: PASS
- M12: PASS

## F. Model Integrity
Model artifacts (`.pkl`, `.joblib`) and financial report aggregates remain unchanged. The `FaultInjector` only intercepts runtime evaluation. 

## G. Financial Integrity
Fault injection does NOT create false recovery or alter M11 methodology. Terminated or failed actions correctly do not record recovered revenue.

## H. Definition of Done
- [x] All 8 required fault types are represented by typed models.
- [x] Fault injection is deterministic.
- [x] Faults can be reset/cleared between tests.
- [x] GATEWAY_OUTAGE has safe retryable behavior.
- [x] API_TIMEOUT has safe uncertain/retryable behavior.
- [x] DUPLICATE_EVENT cannot execute twice.
- [x] ALREADY_PAID prevents intervention.
- [x] MODEL_UNAVAILABLE fails safely without fabricated predictions.
- [x] LLM_UNAVAILABLE has deterministic safe handling.
- [x] POLICY_UNAVAILABLE results in DEFAULT DENY.
- [x] CUSTOMER_OPT_OUT blocks communication.
- [x] Every actually injected fault produces an audit event.
- [x] M10 routes fault outcomes safely.
- [x] M12 UI invokes real fault infrastructure.
- [x] No false recovered revenue is produced by faults.
- [x] M0-M12 regressions remain zero.
- [x] Models/artifacts remain unchanged.
- [x] Ruff passes.
- [x] Formatting passes.
- [x] MyPy passes.
- [x] Full pytest suite passes.

## I. Warnings / Blockers
None. (Existing Joblib Deprecation warnings in the pytest suite are external dependencies and not a blocker).

## J. Next Milestone
Milestone 14 — Advanced Differentiators
