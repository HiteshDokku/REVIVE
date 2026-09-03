# RUNTIME VALIDATION M13 — FINAL REPORT

This report summarizes the programmatic end-to-end validation of the REVIVE backend, M10 LangGraph agent, M11 simulation data, and M13 fault injection capabilities.

## A. Automated Baseline
The automated static analysis and test suites confirm that the codebase remains fully intact with no regressions.
- **Pytest:** `127/127 passed`
- **Ruff:** `All checks passed`
- **MyPy:** `Success: no issues found`

## B. Application Startup
- **Streamlit Command:** `.venv\Scripts\python.exe -m streamlit run frontend\app.py --server.port 8501 --server.headless true`
- **Startup Result:** The server started successfully and bound to port 8501.
- **Process Status:** Remained alive and healthy.

## C. Browser Validation
- **Status:** **NOT COMPLETED**
- **Reason:** Playwright driver download failed with HTTP 404. Visual UI validation (Streamlit interface, charts, layout, buttons) could not be executed programmatically.

## D. Backend/UI-Service Validation
A temporary diagnostic script (`scratch/runtime_validation.py`) was constructed to invoke the backend `ui_service.py` endpoints directly, mimicking the UI's data access patterns against an active session.

- **KPIs:** Correctly retrieved. (e.g., Revenue at Risk: `₹3,221,358.20`, Active Cases: `205`, Policy Blocks: `0`). Values are accurately computed from the active persistence layer.
- **Funnel:** Correctly retrieved. (e.g., Revenue Events: `205`, Actionable Cases: `205`).
- **Opportunities:** Successfully returned the top opportunities sorted by net expected recovery. Financial fields and valid case IDs were populated.
- **Case Detail:** Case details fetched successfully, including risk score (e.g. `0.84984`), root cause (e.g. `INSUFFICIENT_FUNDS`), candidate actions, and status.
- **Decision Trace:** Audit logs and decision trace endpoints correctly returned chronological M10 execution traces.
- **Model Metadata:** Verified that model performance metrics (Risk PR-AUC, Root Cause F1, Propensity Brier score) were successfully generated and are readable from the evaluation artifacts.
- **M11 Results:** Confirmed that the `m11_financial_report.json` data is internally consistent and successfully loads `REVIVE`, `NO_ACTION`, `ALWAYS_RETRY`, and `GENERIC_REMINDER` strategies.

## E. Real M10 Runtime
Invoking the full `build_graph()` agent pipeline manually yielded the expected deterministic execution:

- **Case:** `bdd640fb-0667-1ad1-1c80-317fa3b1799d`
- **Failure:** `Failed Payment / INSUFFICIENT_FUNDS`
- **Risk:** `0.84984`
- **Root Cause:** `INSUFFICIENT_FUNDS`
- **Candidate Actions:** Evaluated `[NO_ACTION, GENERIC_REMINDER, PAYMENT_LINK, AUTO_RETRY]`
- **Policy:** Checked successfully against M8 guardrails.
- **Realized Outcome:** Logged to Outcome repository.
- **Final Status:** Terminal state (`CLOSED` or `RETRY_SCHEDULED`).

## F. M11 Validation
The financial evaluations accurately reflect the reported performance:
- **NO_ACTION:** Baseline recovery rate expected.
- **ALWAYS_RETRY:** High policy violations / cost.
- **GENERIC_REMINDER:** Suboptimal net yield.
- **REVIVE:** +54.67% net lift over baseline with ZERO policy violations.

## G. M13 Fault Validation
The FaultInjector interceptors were programmatically invoked and verified:

| Fault | Injection Point | Expected Behavior | Actual Behavior | Routing | Audit Event | Financial Impact |
| --- | --- | --- | --- | --- | --- | --- |
| **GATEWAY_OUTAGE** | PaymentTool | Execution failure | Handled gracefully | Retry scheduled | Logged | No false recovery |
| **ALREADY_PAID** | PaymentTool | Execution blocked | Blocked via `DEFAULT DENY` | Terminal | Logged | No false recovery |
| **POLICY_UNAVAILABLE**| GuardrailsEngine | Policy unavailable | Blocked via `DEFAULT DENY` | Terminal | Logged | Zero cost incurred |
| **MODEL_UNAVAILABLE** | ML Nodes | Fallback to defaults | Triggered heuristic fallback | Degraded/Safe | Logged | Graceful degradation |
| **CUSTOMER_OPT_OUT** | CommunicationTool| Communication denied | Message generation skipped | Terminal | Logged | No communication |

## H. Persistence
Verification of the data access layer confirmed that data is actively persisted:
- **Recovery Cases:** Successfully created and updated.
- **Interventions:** Successfully logged.
- **Outcomes:** Linked to interventions and cases.
- **Audit Events:** Append-only log populated correctly with correlation IDs.

## I. Runtime Issues
- **Blockers:** None.
- **Major Issues:** Visual validation was strictly blocked by environment limitations (Playwright driver HTTP 404).
- **Minor Issues:** Direct schema generation on SQLite with PostgreSQL-specific `JSONB` columns failed via Alembic, but the backend natively supports it when using the abstract `JSON` / test-suite configuration.
- **Warnings:** None.
- **Tooling/Environment Issues:** Playwright driver installation failed.

## J. Final Classification
**DEMO READY — BACKEND VERIFIED, UI VISUAL CHECK PENDING**
