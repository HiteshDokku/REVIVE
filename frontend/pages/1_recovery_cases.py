import pandas as pd
import streamlit as st
from frontend.components.ui_components import (
    render_empty_state,
    render_error_state,
    render_status_badge,
)

from src.api.services.ui_service import get_all_recovery_cases, get_case_detail
from src.database.connection import get_sync_session_factory

st.set_page_config(page_title="Recovery Cases", page_icon="📋", layout="wide")

st.title("Recovery Cases")
st.markdown("View and filter all active and closed recovery cases.")

SessionLocal = get_sync_session_factory()

with SessionLocal() as session:
    # We can fetch all cases using the new method
    cases = get_all_recovery_cases(session, limit=1000)

if not cases:
    render_empty_state("No recovery cases found in the database.")
else:
    df_cases = pd.DataFrame(cases)

    # Filtering UI
    st.subheader("Filter Cases")
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    with col_f1:
        f_status = st.multiselect("Status", options=df_cases["status"].dropna().unique().tolist())
    with col_f2:
        f_root_cause = st.multiselect(
            "Root Cause", options=df_cases["root_cause"].dropna().unique()
        )
    with col_f3:
        f_action = st.multiselect(
            "Recommended Action", options=df_cases["recommended_action"].dropna().unique()
        )
    with col_f4:
        # Simple text search on customer
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
                "priority": None,  # Hide priority in general view
                "case_id": "Case ID",
                "customer": "Customer",
                "amount_at_risk": st.column_config.NumberColumn("Amount at Risk", format="₹%.2f"),
                "risk_score": st.column_config.NumberColumn("Risk", format="%.2f"),
                "root_cause": "Root Cause",
                "recommended_action": "Recommended Action",
                "expected_recovery": st.column_config.NumberColumn(
                    "Expected Recovery", format="₹%.2f"
                ),
                "expected_net_recovery": st.column_config.NumberColumn(
                    "Expected Net Recovery", format="₹%.2f"
                ),
                "actual_recovered": st.column_config.NumberColumn(
                    "Actual Recovered", format="₹%.2f"
                ),
                "confidence": st.column_config.NumberColumn("Confidence", format="%.2f"),
                "status": "Status",
            },
            hide_index=True,
            use_container_width=True,
        )

    st.divider()

    # --- CASE DETAIL SECTION ---
    st.subheader("Case Detail Explorer")
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
                st.markdown("### Summary")
                st.write(f"**Case ID:** `{c['id']}`")
                st.write(f"**Customer:** {cust['name']} ({cust['email']})")
                st.write(f"**Source:** {c['source_type']}")
                st.write(f"**Amount at Risk:** ₹{c['amount_at_risk']:,.2f}")
                st.write("**Status:**")
                render_status_badge(c["status"])

            with col2:
                st.markdown("### Risk & Root Cause")
                st.write(f"**Risk Score (Probability of Failure):** {c['risk_score']}")
                st.write(f"**Root Cause:** {c['root_cause']}")
                st.write(f"**Root Cause Confidence:** {c['root_cause_confidence']}")
                st.write(f"**Customer Reliability Score:** {cust['reliability_score']}")

            st.markdown("### Candidate Actions & Final Decision")
            candidates = c.get("candidate_actions", [])
            if candidates:
                # Merge recovery predictions if available
                st.write("**Evaluated Candidate Actions:**")
                st.table(candidates)
            else:
                st.info("No candidate actions found in audit trace.")

            st.write(f"**Selected Action:** `{c['recommended_action']}`")
            st.write(f"**Recovery Probability:** {c['recovery_probability']}")
            st.write(f"**Expected Recovery:** ₹{c['expected_recovery']}")
            st.write(f"**Expected Net Recovery:** ₹{c['expected_net_recovery']}")
            st.write(f"**Decision Confidence:** {c['decision_confidence']}")

            li = detail.get("latest_intervention")
            if li:
                st.markdown("### Execution & Policy")
                st.write(f"**Last Action Attempted:** {li['action']}")
                st.write(f"**Action Cost:** ₹{li['cost']}")
                st.write("**Policy Decision:**")
                render_status_badge(li["policy_decision"])
                st.write(f"**Policy Reason:** {li['policy_reason']}")
                st.write(f"**Intervention Status:** {li['status']}")
            else:
                st.info("No interventions have been executed on this case yet.")

            # Link to decision trace
            if st.button("View Full Decision Trace for this Case"):
                st.info(f"Navigate to **Decision Trace** and filter by Case ID: {c['id']}")
        else:
            render_error_state(
                "Case Not Found", f"Could not load details for case {selected_case_id}"
            )
