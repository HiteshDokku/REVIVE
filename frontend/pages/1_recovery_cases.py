import pandas as pd
import streamlit as st

from frontend.components.blade_theme import (
    inject_blade_css,
    render_blade_header,
    render_section_title,
    render_empty_state,
    render_error_state,
    render_badge,
    badge_html,
    card_open,
    card_close,
    kv,
    kv_code,
)
from src.api.services.ui_service import get_all_recovery_cases, get_case_detail
from src.database.connection import get_sync_session_factory

st.set_page_config(page_title="Recovery Cases", page_icon="📋", layout="wide")
inject_blade_css()
render_blade_header("Recovery Cases", "View and filter all active and closed recovery cases.")

SessionLocal = get_sync_session_factory()

with SessionLocal() as session:
    cases = get_all_recovery_cases(session, limit=1000)

if not cases:
    render_empty_state("No recovery cases found in the database.")
else:
    df_cases = pd.DataFrame(cases)

    # ── Filters ───────────────────────────────────────────────────────────
    render_section_title("Filters")
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    with col_f1:
        f_status = st.multiselect("Status", options=df_cases["status"].dropna().unique().tolist())
    with col_f2:
        f_root_cause = st.multiselect("Root Cause", options=df_cases["root_cause"].dropna().unique())
    with col_f3:
        f_action = st.multiselect("Recommended Action", options=df_cases["recommended_action"].dropna().unique())
    with col_f4:
        f_search = st.text_input("Search Customer")

    filtered_df = df_cases.copy()
    if f_status:
        filtered_df = filtered_df[filtered_df["status"].isin(f_status)]
    if f_root_cause:
        filtered_df = filtered_df[filtered_df["root_cause"].isin(f_root_cause)]
    if f_action:
        filtered_df = filtered_df[filtered_df["recommended_action"].isin(f_action)]
    if f_search:
        filtered_df = filtered_df[filtered_df["customer"].str.contains(f_search, case=False)]

    if filtered_df.empty:
        render_empty_state("No cases match your filter criteria.")
    else:
        st.dataframe(
            filtered_df,
            column_config={
                "priority": None,
                "case_id": "Case ID",
                "customer": "Customer",
                "amount_at_risk": st.column_config.NumberColumn("Amount at Risk", format="₹%.2f"),
                "risk_score": st.column_config.NumberColumn("Risk", format="%.2f"),
                "root_cause": "Root Cause",
                "recommended_action": "Recommended Action",
                "expected_recovery": st.column_config.NumberColumn("Expected Recovery", format="₹%.2f"),
                "expected_net_recovery": st.column_config.NumberColumn("Net Recovery", format="₹%.2f"),
                "actual_recovered": st.column_config.NumberColumn("Actual Recovered", format="₹%.2f"),
                "confidence": st.column_config.NumberColumn("Confidence", format="%.2f"),
                "status": "Status",
},
            hide_index=True,
            use_container_width=True,
        )

    st.divider()

    # ── Case Detail ───────────────────────────────────────────────────────
    render_section_title("Case Detail Explorer")
    selected_case_id = st.selectbox(
        "Select a Case ID to view details", options=filtered_df["case_id"].tolist()
    )

    if selected_case_id:
        with SessionLocal() as session:
            detail = get_case_detail(session, selected_case_id)

        if detail:
            c = detail["case"]
            cust = detail["customer"]

            col1, col2 = st.columns(2)
            with col1:
                card_open("Summary")
                st.markdown(
                    kv_code("Case ID", c["id"])
                    + kv("Customer", f"{cust['name']} ({cust['email']})")
                    + kv("Source", c["source_type"])
                    + kv("Amount at Risk", f"₹{c['amount_at_risk']:,.2f}"),
                    unsafe_allow_html=True,
                )
                st.write("**Status:**")
                render_badge(c["status"])
                card_close()

            with col2:
                card_open("Risk & Root Cause")
                st.markdown(
                    kv("Risk Score", str(c["risk_score"]))
                    + kv("Root Cause", c["root_cause"])
                    + kv("Root Cause Confidence", str(c["root_cause_confidence"]))
                    + kv("Customer Reliability", str(cust["reliability_score"])),
                    unsafe_allow_html=True,
                )
                card_close()

            card_open("Candidate Actions & Final Decision")
            candidates = c.get("candidate_actions", [])
            if candidates:
                st.write("**Evaluated Candidate Actions:**")
                st.table(candidates)
            else:
                st.info("No candidate actions found in audit trace.")

            st.markdown(
                kv_code("Selected Action", c["recommended_action"])
                + kv("Recovery Probability", str(c["recovery_probability"]))
                + kv("Expected Recovery", f"₹{c['expected_recovery']}")
                + kv("Expected Net Recovery", f"₹{c['expected_net_recovery']}")
                + kv("Decision Confidence", str(c["decision_confidence"])),
                unsafe_allow_html=True,
            )
            card_close()

            li = detail.get("latest_intervention")
            if li:
                card_open("Execution & Policy")
                st.markdown(
                    kv("Last Action", li["action"])
                    + kv("Action Cost", f"₹{li['cost']}"),
                    unsafe_allow_html=True,
                )
                st.write("**Policy Decision:**")
                render_badge(li["policy_decision"])
                st.markdown(
                    kv("Policy Reason", li["policy_reason"])
                    + kv("Intervention Status", li["status"]),
                    unsafe_allow_html=True,
                )
                card_close()
            else:
                st.info("No interventions have been executed on this case yet.")

            if st.button("View Full Decision Trace for this Case"):
                st.info(f"Navigate to **Decision Trace** and filter by Case ID: {c['id']}")
        else:
            render_error_state(
                "Case Not Found", f"Could not load details for case {selected_case_id}"
            )
