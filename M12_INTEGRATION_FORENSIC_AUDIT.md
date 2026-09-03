# M12 INTEGRATION FORENSIC AUDIT

## Executive Summary
**FAIL** for M12 runtime integration.

While the backend logic and tests are sound, the Streamlit application is disconnected from the real execution pipeline. It surfaces uninitialized placeholder data from the synthetic generator because the M10 agent graph is never invoked on the database cases. Furthermore, critical UI features (Simulation Lab, Model Performance) are either hardcoded to static files or look for incorrect filenames, completely bypassing the backend services.

## Finding Matrix

| Problem | Root Cause | Evidence | Severity |
|---------|------------|----------|----------|
| **Expected Recovery = 0** | DB cases uninitialized by M10 | `src/data/synthetic/cases.py` hardcodes `expected_recovery=0.0`. M10 is never run to update it. | HIGH |
| **Only Retry** | Hardcoded placeholder | `cases.py` hardcodes `recommended_action="RETRY_LATER"`. | HIGH |
| **Confidence = 0** | Hardcoded placeholder | `cases.py` hardcodes `decision_confidence=0.0`. | HIGH |
| **Decision Trace missing** | Zero audit events in DB | `audit_events` table has 0 rows because M10 never executed on these cases. | HIGH |
| **Audit Explorer empty** | Zero audit events in DB | `audit_events` table has 0 rows. | HIGH |
| **Simulation static** | UI hardcodes report reading | `frontend/pages/3_simulation_lab.py` uses `with open("artifacts/evaluations/m11_financial_report.json")`, ignoring all UI parameters. | CRITICAL |
| **Model metadata missing** | Filename mismatch | UI expects `risk_model_metadata.json` but artifact is `revenue_risk_metadata.json`. | MEDIUM |

## Architecture Integrity
**M0-M13 business logic remains completely untouched and intact.**
The failures are purely isolated to M12 UI-to-Backend integration and startup data hydration. The backend simulator, decision engine, models, and M10 LangGraph agent function correctly in isolation (as verified by the tests and previous programmatic validation), but they are not being invoked by the running Streamlit application.

## 1. Database Forensics
* **DATABASE URL / backend:** `sqlite:///./data/revive_dev.db` (via config default)
* **Database file if SQLite:** `data/revive_dev.db`
* **Environment variables used:** None (`.env` missing, falling back to Pydantic defaults)
* **Connection/session factory:** `get_sync_session_factory` (via `src.database.connection`)
* **Row Counts:**
  - `customers`: 100
  - `subscriptions`: 0
  - `payments`: 657
  - `invoices`: 0
  - `recovery_cases`: 205
  - `interventions`: 0
  - `outcomes`: 0
  - `audit_events`: 0
* **Newest case timestamp:** `2023-06-30 23:30:00` (Synthetic)
* **Visibility:** Control Tower actively queries this database (reading the 205 active cases).

## 2. Recovery Case Forensics
Tracking real case `bdd640fb-0667-1ad1-1c80-317fa3b1799d`:

| Field | Backend source | Persisted? | UI service reads? | UI displays? |
|-------|----------------|------------|-------------------|--------------|
| Risk inference | Synthetic Gen | Yes | Yes | Yes |
| Risk probability | Synthetic Gen | Yes | Yes | Yes |
| Root cause | Synthetic Gen | Yes | Yes | Yes |
| Root cause confidence | Synthetic Gen | Yes | Yes | Yes |
| Candidate actions | M7 | No (No DB col) | No | No |
| Recovery probabilities | M6 / M7 | No (No DB col) | No | No |
| Expected recovery | M7 / M10 | Yes (as 0.00) | Yes | Yes |
| Action cost | M7 / M8 | No | No | No |
| Expected net recovery | M7 / M10 | Yes (as 0.00) | Yes | Yes |
| Selected action | Synthetic Gen | Yes (RETRY_LATER) | Yes | Yes |
| Policy result | M8 Guardrails | No (in Audits) | No | No |
| Execution result | M10 Tools | No (in Audits) | No | No |
| Outcome | M10 / Simulator | No (0 rows) | Yes | Yes (as 0) |
| Recovered amount | Outcome | No | Yes | Yes (as 0) |
| Audit events | M10 Graph | No (0 rows) | Yes | Yes (Empty) |

## 3. Why Only Retry?
Candidate actions are correctly evaluated in `CandidateActionGenerator` (M7) within the backend pipeline. However, the database schema only provides a scalar `recommended_action` column. Because the cases in the database were populated by the synthetic generator and the M10 agent was never executed over them, the DB retains the synthetic placeholder `"RETRY_LATER"` (from `cases.py` line 78). The UI Service simply queries this static placeholder.

## 4. Why Expected Recovery = 0?
In `src/data/synthetic/cases.py` line 79, `expected_recovery` is hardcoded to `Decimal("0.0")` with a comment *"Will be updated by propensity model later"*. Because the M10 pipeline is never run on startup or on demand from the UI to process the backlog, the values remain exactly `0.0`.

## 5. Why Confidence = 0?
Similar to Expected Recovery, `cases.py` line 81 hardcodes `decision_confidence = Decimal("0.0")`.

## 6. Decision Trace Forensics
* **Are audit events being created?** No. The `audit_events` table contains exactly 0 rows.
* **Why the UI cannot display the trace:** `ui_service.get_decision_trace(case_id)` queries `AuditEvent` for the target case. Since the M10 LangGraph node execution has never occurred for the cases residing in `revive_dev.db`, there are no audit traces to return.

## 7. Why Audit Explorer Is Empty
**A. The database truly contains zero audit events.**
The UI queries the correct database and `ui_service` function correctly, but the table is empty because no interventions have been executed.

## 8. Simulation Lab Forensics
* **UI Behavior:** **Case 2** (Loads static file).
* Changing parameters in the UI (e.g. customer count, seed, scenario) does **NOT** reach `EvaluationEngine` or any real backend service.
* `frontend/pages/3_simulation_lab.py` explicitly bypasses the backend and executes:
  `with open("artifacts/evaluations/m11_financial_report.json") as f: json.load(f)`
* **Proof:** Modifying the PRNG Seed in the UI instantly re-renders the same hardcoded head-to-head metrics without executing a backend evaluation.

## 9. Model Metadata Forensics
* **Expected by UI:** `risk_model_metadata.json` and `root_cause_model_metadata.json`
* **Actual Filenames:** `revenue_risk_metadata.json` and `root_cause_metadata.json`
* **Schema Match:** The UI looks for `"evaluation_metrics" : {"roc_auc", "pr_auc", ...}`. The actual files use `"metrics": {"roc_auc", "pr_auc", ...}`.
* **Conclusion:** The metrics exist and the models are real, but the UI component expects outdated filenames and schemas.

## 10. Control Tower Forensics
* **Revenue at Risk:** Reads `sum(amount_at_risk)` for OPEN cases. Current value matches DB cases (e.g., ₹3.2M).
* **Expected Recovery:** Reads `sum(expected_net_recovery)`. Returns 0 because all DB cases are hardcoded to 0 by the synthetic generator.
* **Recovered Revenue:** Returns 0 because there are 0 successful Outcomes.
* **Incremental Revenue:** Statically parsed from the M11 financial report JSON (REVIVE mean vs ALWAYS_RETRY mean).

## 11. Test-vs-Runtime Investigation
* **Tests (127 passed):** Unit and integration tests run against an isolated `sqlite:///:memory:` database and directly invoke the `M10` and `ui_service` methods using accurately populated test fixtures or mock data.
* **Runtime:** The Streamlit app runs against `data/revive_dev.db`. The integration gap is that this database is populated with raw un-processed cases, and the application lacks a "run agent pipeline" trigger to actually process these cases, generate the audits, and update the metrics. The UI relies on data that the backend is fully capable of generating but was never commanded to generate.

## 12. Startup Environment
* **Pytest Environment:** In-memory transient database. Services instantiated in isolation.
* **Streamlit Environment:** Connects to `sqlite:///./data/revive_dev.db`. Runs persistently, but passively waiting for backend processes that are dormant.

## Required Fixes (DO NOT IMPLEMENT YET)

1. **M11 integration bug:** Connect the `Simulation Lab` UI controls to actually trigger `EvaluationEngine.run()` instead of reading a static JSON.
2. **M12 integration bug:** Fix filename (`revenue_risk` vs `risk_model`) and schema (`metrics` vs `evaluation_metrics`) mismatches in `5_model_performance.py`.
3. **M10 persistence bug / Environment issue:** The application requires a startup mechanism (or a UI trigger) to run the `M10` LangGraph agent against the `OPEN` cases in the DB, replacing the `0.0` and `RETRY_LATER` synthetic defaults with real decisions and populating the `audit_events` and `outcomes` tables.
4. **M12 integration bug:** `ui_service.py` lacks queries for candidate action arrays, relying entirely on the scalar `recommended_action` DB column.
