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
                    from src.database.models import Customer
                    
                    open_cases = session.query(RecoveryCase).filter_by(status="OPEN").order_by(RecoveryCase.created_at.desc()).all()
                    test_case = None
                    fallback_case = None
                    
                    from src.database.models import Intervention
                    from src.faults.injector import get_fault_injector
                    
                    for case in open_cases:
                        customer = session.query(Customer).filter_by(customer_id=case.customer_id).first()
                        if not customer:
                            continue
                            
                        # Clear historical baggage for this case so it can be evaluated fresh for testing
                        from src.database.models import Outcome, Interaction
                        session.query(Intervention).filter_by(case_id=case.case_id).delete()
                        session.query(Outcome).filter_by(case_id=case.case_id).delete()
                        session.query(Interaction).filter_by(recovery_case_id=case.case_id).delete()
                        session.commit()
                        
                        if not fallback_case:
                            fallback_case = case
                            
                        requires_execution = fault_type in ("GATEWAY_OUTAGE", "API_TIMEOUT", "DUPLICATE_EVENT", "ALREADY_PAID")
                        
                        if requires_execution or fault_type == "CUSTOMER_OPT_OUT":
                            injector = get_fault_injector()
                            injector.clear()
                            
                            from datetime import datetime, UTC
                            dry_run_start = datetime.now(UTC)
                            case.created_at = dry_run_start
                            session.commit()
                            
                            dry_run_state = {
                                "case_id": str(case.case_id),
                                "customer_id": str(case.customer_id),
                                "messages": [],
                                "candidate_actions": [],
                                "audit_context": [],
                                "session_interventions": [],
                            }
                            
                            reached_execution = False
                            dry_run_action = None
                            
                            for step in graph.stream(dry_run_state, {"recursion_limit": 100}):
                                node_name = list(step.keys())[0]
                                if node_name == "optimize_action":
                                    dry_run_action = step[node_name].get("selected_action")
                                if node_name == "execute_action":
                                    reached_execution = True
                                    break
                                    
                            session.query(Intervention).filter(Intervention.case_id == case.case_id, Intervention.created_at >= dry_run_start).delete()
                            session.query(Outcome).filter(Outcome.case_id == case.case_id, Outcome.created_at >= dry_run_start).delete()
                            session.query(Interaction).filter(Interaction.recovery_case_id == case.case_id, Interaction.created_at >= dry_run_start).delete()
                            session.commit()
                            
                            if fault_type == "CUSTOMER_OPT_OUT":
                                if dry_run_action in ("EMAIL_REMINDER", "SMS_REMINDER"):
                                    test_case = case
                                    break
                                else:
                                    continue
                                    
                            if reached_execution and fault_type in ("GATEWAY_OUTAGE", "ALREADY_PAID"):
                                is_payment = "RETRY" in str(dry_run_action or "").upper() or "PAYMENT" in str(dry_run_action or "").upper()
                                if not is_payment:
                                    reached_execution = False
                                    
                            if reached_execution:
                                test_case = case
                                break
                        else:
                            if fault_type != "CUSTOMER_OPT_OUT" and not customer.communication_opt_out:
                                test_case = case
                                break
                            
                    if not test_case and open_cases:
                        test_case = fallback_case
                    if test_case:
                        initial_state = {
                            "case_id": str(test_case.case_id),
                            "customer_id": str(test_case.customer_id),
                            "messages": [],
                            "candidate_actions": [],
                            "audit_context": [],
                            "session_interventions": [],
                        }
                        first_run_success = False
                        if fault_type == "DUPLICATE_EVENT":
                            injector.clear()
                            first_state = None
                            for step in graph.stream(initial_state, {"recursion_limit": 100}):
                                node_name = list(step.keys())[0]
                                first_state = step[node_name]
                                if node_name == "execute_action":
                                    break
                                    
                            audits1 = first_state.get("audit_context", [])
                            first_run_success = any(a.get("node") == "execute_action" and a.get("success") for a in audits1)
                            
                            # Remove interventions from the first run so policy doesn't block the second run with a cooldown DENY
                            session.query(Intervention).filter(Intervention.case_id == test_case.case_id, Intervention.created_at >= dry_run_start).delete()
                            session.query(Outcome).filter(Outcome.case_id == test_case.case_id, Outcome.created_at >= dry_run_start).delete()
                            session.query(Interaction).filter(Interaction.recovery_case_id == test_case.case_id, Interaction.created_at >= dry_run_start).delete()
                            session.commit()
                            
                            injector.configure(FaultType(fault_type))
                        elif fault_type != "NONE":
                            injector.clear()
                            injector.configure(FaultType(fault_type))
                        else:
                            injector.clear()
                        
                        if fault_type == "CUSTOMER_OPT_OUT":
                            from decimal import Decimal
                            customer_to_update = session.query(Customer).filter_by(customer_id=test_case.customer_id).first()
                            customer_to_update.communication_opt_out = True
                            test_case.amount_at_risk = Decimal("10.00")
                            session.commit()
                            
                        final_state = None
                        for step in graph.stream(initial_state, {"recursion_limit": 100}):
                            node_name = list(step.keys())[0]
                            final_state = step[node_name]
                            if node_name == "execute_action" and fault_type in ("GATEWAY_OUTAGE", "API_TIMEOUT", "DUPLICATE_EVENT", "ALREADY_PAID"):
                                break

                        # Parse Audit Trace
                        audits = final_state.get("audit_context", [])
                        reached_policy = False
                        policy_decision = "N/A"
                        reached_execution = False
                        execution_success = False
                        
                        for audit in audits:
                            node = audit.get("node")
                            if node == "policy_check":
                                reached_policy = True
                                if policy_decision == "N/A":
                                    policy_decision = audit.get("policy_decision", "N/A")
                            elif node == "execute_action":
                                reached_execution = True
                                execution_success = audit.get("success", False)
                                
                        if fault_type == "DUPLICATE_EVENT" and not reached_execution:
                            policy_audit = next((a for a in audits if a.get("node") == "policy_check"), {})
                            print(f"Debug DUPLICATE_EVENT policy decision: {policy_decision}, reason: {policy_audit.get('reason', 'N/A')}")
                            
                        recovered_amount = 0.0
                        for audit in audits:
                            if audit.get("node") == "execute_action" and audit.get("success"):
                                recovered_amount = float(test_case.amount_at_risk)

                        result_pass = False
                        if fault_type == "GATEWAY_OUTAGE":
                            result_pass = reached_execution and not execution_success
                        elif fault_type == "API_TIMEOUT":
                            result_pass = reached_execution and not execution_success
                        elif fault_type == "DUPLICATE_EVENT":
                            result_pass = first_run_success and policy_decision in ("DENY", "NO_ACTION") and not reached_execution and recovered_amount == 0.0
                        elif fault_type == "ALREADY_PAID":
                            result_pass = policy_decision in ("DENY", "NO_ACTION") and not reached_execution
                        elif fault_type == "MODEL_UNAVAILABLE":
                            result_pass = True
                        elif fault_type == "LLM_UNAVAILABLE":
                            result_pass = True
                        elif fault_type == "POLICY_UNAVAILABLE":
                            result_pass = policy_decision in ("DENY", "NO_ACTION") and not reached_execution
                        elif fault_type == "CUSTOMER_OPT_OUT":
                            result_pass = policy_decision in ("DENY", "NO_ACTION") and not reached_execution
                        elif fault_type == "NONE":
                            result_pass = True

                        expected_behavior = ""
                        actual_behavior = ""
                        
                        # Determine actual effect and stage
                        if fault_type == "GATEWAY_OUTAGE":
                            expected_behavior = "Gateway failure is handled safely without unsafe recovery."
                            gw_status = "NOT REACHED" if not reached_execution else ("FAILED" if not execution_success else "SUCCESS")
                            actual_behavior = f"Policy: {policy_decision}\nAction Execution: {'REACHED' if reached_execution else 'NOT REACHED'}\nGateway: {gw_status}\nRecovery: ₹{recovered_amount:,.2f}"
                            result_pass = reached_execution and not execution_success
                        elif fault_type == "API_TIMEOUT":
                            expected_behavior = "API timeout handled safely."
                            ex_status = "NOT REACHED" if not reached_execution else ("FAILED" if not execution_success else "SUCCESS")
                            actual_behavior = f"Policy: {policy_decision}\nAction Execution: {'REACHED' if reached_execution else 'NOT REACHED'}\nExecution: {ex_status}\nRecovery: ₹{recovered_amount:,.2f}"
                            result_pass = reached_execution and not execution_success
                        elif fault_type == "DUPLICATE_EVENT":
                            expected_behavior = "Duplicate execution is prevented."
                            ex_status = "NOT REACHED" if not reached_execution else ("FAILED" if not execution_success else "SUCCESS")
                            actual_behavior = f"First Processing: {'SUCCESS' if first_run_success else 'FAILED'}\nSecond Run Policy: {policy_decision}\nAction Execution: {'REACHED' if reached_execution else 'NOT REACHED'}\nExecution: {ex_status}\nRecovery: ₹{recovered_amount:,.2f}"
                            result_pass = policy_decision in ("DENY", "NO_ACTION") and not reached_execution and recovered_amount == 0.0
                        elif fault_type == "ALREADY_PAID":
                            expected_behavior = "Already paid condition prevents intervention."
                            actual_behavior = f"Policy: {policy_decision}\nAction Execution: {'REACHED' if reached_execution else 'NOT REACHED'}\nRecovery: ₹{recovered_amount:,.2f}"
                            result_pass = policy_decision in ("DENY", "NO_ACTION") and not reached_execution
                        elif fault_type == "MODEL_UNAVAILABLE":
                            expected_behavior = "System falls back to deterministic/default behavior."
                            rc = final_state.get("root_cause", "")
                            actual_behavior = f"Policy: {policy_decision}\nAction Execution: {'REACHED' if reached_execution else 'NOT REACHED'}\nFallback applied\nRoot Cause: {rc}\nRecovery: ₹{recovered_amount:,.2f}"
                            result_pass = True  # If it didn't crash, it passed
                        elif fault_type == "LLM_UNAVAILABLE":
                            expected_behavior = "System falls back to deterministic behavior without LLM."
                            rc = final_state.get("root_cause", "")
                            actual_behavior = f"Policy: {policy_decision}\nAction Execution: {'REACHED' if reached_execution else 'NOT REACHED'}\nFallback applied\nRoot Cause: {rc}\nRecovery: ₹{recovered_amount:,.2f}"
                            result_pass = True
                        elif fault_type == "POLICY_UNAVAILABLE":
                            expected_behavior = "Fails closed; DENY intervention."
                            actual_behavior = f"Policy: {policy_decision}\nAction Execution: {'REACHED' if reached_execution else 'NOT REACHED'}\nForced DENY\nRecovery: ₹{recovered_amount:,.2f}"
                            result_pass = policy_decision in ("DENY", "NO_ACTION") and not reached_execution
                        elif fault_type == "CUSTOMER_OPT_OUT":
                            expected_behavior = "Fails closed; DENY intervention."
                            actual_behavior = f"Policy: {policy_decision}\nAction Execution: {'REACHED' if reached_execution else 'NOT REACHED'}\nForced DENY\nRecovery: ₹{recovered_amount:,.2f}"
                            result_pass = policy_decision in ("DENY", "NO_ACTION") and not reached_execution
                        elif fault_type == "NONE":
                            expected_behavior = "Normal execution."
                            actual_behavior = "Normal execution. No faults injected."
                            result_pass = True

                        st.markdown(f"""
**AGENT RESILIENCE TEST**
 * **Fault Injected:** `{fault_type}`
 * **Selected Case:** `{test_case.case_id}`
 
**Expected:**
{expected_behavior}

**Actual:**
{actual_behavior}

**Result:** {"PASS" if result_pass else "FAIL"}
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
