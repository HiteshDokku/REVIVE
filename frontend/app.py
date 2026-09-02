import pandas as pd
import plotly.express as px
import streamlit as st

from frontend.components.ui_components import (
    render_empty_state,
    render_error_state,
)
from src.api.services.ui_service import get_kpi_metrics, get_revenue_funnel, get_top_opportunities
from src.database.connection import get_sync_session_factory

st.set_page_config(
    page_title="REVIVE Control Tower",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("REVIVE")
st.subheader("Autonomous Revenue Recovery & Intervention Engine")

SessionLocal = get_sync_session_factory()

# Load Data
with SessionLocal() as session:
    kpis = get_kpi_metrics(session)
    funnel = get_revenue_funnel(session)
    top_opps = get_top_opportunities(session, limit=10)


# --- DEMO CONTROLS ---
with st.expander("🛠️ Demo Controls & Interventions"):
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Run Recovery", use_container_width=True):
            with st.spinner("Running M10 Agent Graph on active cases..."):
                from sqlalchemy import select

                from src.agent.graph import graph
                from src.database.models import RecoveryCase

                with SessionLocal() as s:
                    cases = s.scalars(
                        select(RecoveryCase).where(RecoveryCase.status.in_(["OPEN", "IN_PROGRESS"]))
                    ).all()
                    case_ids = [str(c.case_id) for c in cases]

                if not case_ids:
                    st.info("No active cases to process.")
                else:
                    for cid in case_ids:
                        try:
                            graph.invoke({"case_id": cid})
                        except Exception as e:
                            st.error(f"Error on {cid}: {e}")
                    st.success(f"Recovery pipeline initiated for {len(case_ids)} cases.")
                    st.rerun()
        if st.button("Run Simulation", use_container_width=True):
            st.switch_page("pages/3_simulation_lab.py")
    with col2:
        fault_type = st.selectbox(
            "Select Fault to Inject",
            [
                "NONE",
                "GATEWAY_OUTAGE",
                "API_TIMEOUT",
                "DUPLICATE_EVENT",
                "ALREADY_PAID",
                "LLM_UNAVAILABLE",
                "MODEL_UNAVAILABLE",
                "POLICY_UNAVAILABLE",
                "CUSTOMER_OPT_OUT",
            ],
        )
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            if st.button("Run Agent Resilience Test", use_container_width=True):
                try:
                    from src.agent.graph import graph
                    from src.database.connection import get_sync_session_factory
                    from src.database.models import RecoveryCase
                    from src.faults.injector import get_fault_injector
                    from src.faults.models import FaultType

                    injector = get_fault_injector()
                    injector.clear()
                    if fault_type != "NONE":
                        injector.configure(FaultType(fault_type))

                    session = get_sync_session_factory()()
                    test_case = session.query(RecoveryCase).filter_by(status="OPEN").first()
                    if test_case:
                        initial_state = {
                            "case_id": str(test_case.case_id),
                            "customer_id": str(test_case.customer_id),
                            "messages": [],
                            "candidate_actions": [],
                            "audit_context": [],
                            "session_interventions": [],
                        }
                        final_state = graph.invoke(initial_state, {"recursion_limit": 100})

                        # Parse Audit Trace
                        audits = final_state.get("audit_context", [])
                        reached_policy = False
                        policy_decision = "N/A"
                        reached_execution = False
                        execution_success = False
                        recovered_amount = 0.0
                        fault_effect = "None observed."

                        for audit in audits:
                            node = audit.get("node")
                            if node == "policy_check":
                                reached_policy = True
                                policy_decision = audit.get("policy_decision", "N/A")
                            elif node == "execute_action":
                                reached_execution = True
                                execution_success = audit.get("success", False)
                                if execution_success:
                                    recovered_amount = float(test_case.amount_at_risk)

                        # Determine actual effect and stage
                        if fault_type == "GATEWAY_OUTAGE":
                            if not reached_execution:
                                fault_effect = f"Gateway outage fault injected, but agent did not reach execution stage. (Policy Decision: {policy_decision})"
                            else:
                                fault_effect = f"Gateway outage intercepted execute_action. Execution forced to fail (Success: {execution_success})."
                        elif fault_type == "MODEL_UNAVAILABLE":
                            rc = final_state.get("root_cause", "")
                            fault_effect = (
                                f"Model unavailable. Fallback applied. Root Cause Output: {rc}"
                            )
                        elif fault_type == "POLICY_UNAVAILABLE":
                            fault_effect = (
                                f"Policy engine unavailable. Forced Decision: {policy_decision}"
                            )
                        elif fault_type == "CUSTOMER_OPT_OUT":
                            fault_effect = (
                                f"Customer Opt-Out triggered. Forced Decision: {policy_decision}"
                            )
                        elif fault_type == "NONE":
                            fault_effect = "Normal execution. No faults injected."

                        st.markdown(f"""
**AGENT RESILIENCE TEST**
 ***Fault Injected:** {fault_type}
 * **Tested Case:** `{test_case.case_id}`

**Actual Graph Execution Results:**
 * **Reached Policy Check:** {reached_policy}
 * **Policy Decision:** {policy_decision}
 * **Reached Action Execution:** {reached_execution}
 * **Execution Success:** {execution_success}
 * **Amount Recovered:** ₹{recovered_amount:,.2f}

**Fault/Error Effect:**
{fault_effect}
                        """)
                    else:
                        st.success(
                            f"Fault {fault_type} configured globally (no OPEN test case available)."
                        )
                except Exception as e:
                    render_error_state("Fault Error", str(e))
        with col_f2:
            if st.button("Clear Faults", use_container_width=True):
                from src.faults.injector import get_fault_injector

                get_fault_injector().clear()
                st.success("Faults cleared.")
    with col3:
        if st.button("Refresh Data", use_container_width=True):
            st.rerun()

st.divider()

# --- KPI CARDS ---
# Use a responsive flex container instead of strict st.columns to prevent truncation
kpi_html = f"""
<style>
.kpi-container {{
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    margin-bottom: 2rem;
}}
.kpi-card {{
    flex: 1 1 15%;
    min-width: 150px;
    background-color: #1e1e1e;
    padding: 1rem;
    border-radius: 0.5rem;
    border: 1px solid #333;
}}
.kpi-title {{
    font-size: 0.9rem;
    color: #a0a0a0;
    margin-bottom: 0.5rem;
}}
.kpi-value {{
    font-size: 1.5rem;
    font-weight: 600;
    color: #ffffff;
    white-space: nowrap;
}}
@media (max-width: 1200px) {{
    .kpi-card {{ flex: 1 1 30%; }}
}}
@media (max-width: 768px) {{
    .kpi-card {{ flex: 1 1 100%; }}
}}
</style>
<div class="kpi-container">
    <div class="kpi-card">
        <div class="kpi-title">Revenue at Risk</div>
        <div class="kpi-value">₹{kpis["revenue_at_risk"]:,.2f}</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-title" title="Predicted net recovery for all active cases">Expected Recovery (Active)</div>
        <div class="kpi-value">₹{kpis["expected_recovery"]:,.2f}</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-title" title="Actual revenue successfully realized from closed cases">Actual Recovered Revenue (Outcome-level)</div>
        <div class="kpi-value">₹{kpis["recovered_revenue"]:,.2f}</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-title">Incremental Revenue</div>
        <div class="kpi-value">₹{kpis["incremental_revenue"]:,.2f}</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-title">Active Cases (Case-level)</div>
        <div class="kpi-value">{kpis["active_cases"]}</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-title">Blocked Cases (Case-level)</div>
        <div class="kpi-value">{kpis["policy_blocks"]}</div>
    </div>
</div>
"""
st.markdown(kpi_html, unsafe_allow_html=True)

st.divider()

# --- REVENUE FUNNEL & CHARTS ---
st.subheader("Revenue Funnel & Risk Profile")
col_f1, col_f2 = st.columns(2)

with col_f1:
    if funnel["revenue_events"] == 0:
        render_empty_state("No revenue events found to generate funnel.")
    else:
        funnel_df = pd.DataFrame(
            [
                {"Stage": "Total Cases (Case-level)", "Count": funnel["revenue_events"]},
                {"Stage": "Actionable Cases (Case-level)", "Count": funnel["actionable_cases"]},
                {
                    "Stage": "Approved Interventions (Intervention-level)",
                    "Count": funnel["approved_interventions"],
                },
                {
                    "Stage": "Successful Recoveries (Outcome-level)",
                    "Count": funnel["successful_recoveries"],
                },
            ]
        )
        fig = px.funnel(funnel_df, x="Count", y="Stage", title="Recovery Pipeline Conversion")
        st.plotly_chart(fig, use_container_width=True)

with col_f2:
    if not top_opps:
        render_empty_state("No active cases available to build risk profile.")
    else:
        # We can build a quick risk distribution chart from top opportunities or general active cases
        df_risk = pd.DataFrame(top_opps)
        if "amount_at_risk" in df_risk.columns and "risk_score" in df_risk.columns:
            # Convert decimal to float for plotly
            df_risk["amount_at_risk"] = df_risk["amount_at_risk"].astype(float)
            df_risk["risk_score"] = df_risk["risk_score"].astype(float)
            fig_risk = px.scatter(
                df_risk,
                x="risk_score",
                y="amount_at_risk",
                title="Risk vs Value (Top Cases)",
                hover_data=["customer", "root_cause"],
            )
            st.plotly_chart(fig_risk, use_container_width=True)

st.divider()

# --- TOP OPPORTUNITIES ---
st.subheader("Top Opportunities")
if not top_opps:
    render_empty_state("No active recovery cases to display.")
else:
    df_opps = pd.DataFrame(top_opps)
    # Format currency for display
    df_opps["amount_at_risk"] = df_opps["amount_at_risk"].apply(
        lambda x: f"₹{x:,.2f}" if x else "₹0.00"
    )
    df_opps["expected_recovery"] = df_opps["expected_recovery"].apply(
        lambda x: f"₹{x:,.2f}" if x else "₹0.00"
    )
    df_opps["expected_net_recovery"] = df_opps["expected_net_recovery"].apply(
        lambda x: f"₹{x:,.2f}" if x else "₹0.00"
    )

    st.dataframe(
        df_opps,
        column_config={
            "priority": "Priority",
            "case_id": "Case ID",
            "customer": "Customer",
            "amount_at_risk": "Amount at Risk",
            "risk_score": st.column_config.NumberColumn("Risk", format="%.2f"),
            "root_cause": "Root Cause",
            "recommended_action": "Recommended Action",
            "expected_recovery": "Expected Recovery",
            "expected_net_recovery": "Expected Net Recovery",
            "confidence": st.column_config.NumberColumn("Confidence", format="%.2f"),
            "status": "Status",
        },
        hide_index=True,
        use_container_width=True,
    )

    st.info("Navigate to **Recovery Cases** in the sidebar to view full case details.")
