import pandas as pd
import streamlit as st
from frontend.components.ui_components import render_empty_state

from src.api.services.ui_service import get_audit_logs
from src.database.connection import get_sync_session_factory

st.set_page_config(page_title="Audit Explorer", page_icon="📜", layout="wide")

st.title("Audit Explorer")
st.markdown("Searchable and filterable log of system audit events.")

SessionLocal = get_sync_session_factory()
with SessionLocal() as session:
    logs = get_audit_logs(session, limit=500)

if not logs:
    render_empty_state("No audit events found in the database.")
else:
    df_logs = pd.DataFrame(logs)

    st.subheader("Filters")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        f_type = st.multiselect("Event Type", options=df_logs["event_type"].unique())
    with c2:
        f_actor = st.multiselect("Actor", options=df_logs["actor"].unique())
    with c3:
        f_case = st.text_input("Filter by Case ID")
    with c4:
        f_corr = st.text_input("Filter by Correlation ID")

    filtered = df_logs.copy()
    if f_type:
        filtered = filtered[filtered["event_type"].isin(f_type)]
    if f_actor:
        filtered = filtered[filtered["actor"].isin(f_actor)]
    if f_case:
        # Handle cases where case_id might be None
        filtered = filtered[filtered["case_id"].fillna("").str.contains(f_case, case=False)]
    if f_corr:
        filtered = filtered[filtered["correlation_id"].str.contains(f_corr, case=False)]

    if filtered.empty:
        render_empty_state("No logs match your filter criteria.")
    else:
        st.dataframe(
            filtered,
            column_config={
                "event_id": "Event ID",
                "case_id": "Case ID",
                "event_type": "Event Type",
                "event_time": st.column_config.DatetimeColumn(
                    "Timestamp", format="YYYY-MM-DD HH:mm:ss"
                ),
                "actor": "Actor",
                "correlation_id": "Correlation ID",
                "decision": None,  # Hide complex JSON objects from standard table view
                "policy_result": None,
                "execution_result": None,
            },
            hide_index=True,
            use_container_width=True,
        )
