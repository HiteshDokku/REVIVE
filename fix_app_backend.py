app_path = r"frontend\app.py"
with open(app_path, encoding="utf-8") as f:
    content = f.read()

old_run = """        if st.button("Run Recovery", use_container_width=True):
            with st.spinner("Running M10 Agent Graph..."):
                # Placeholder for actual backend invocation, but UI must not fake it.
                st.success("Recovery pipeline initiated.")"""

new_run = """        if st.button("Run Recovery", use_container_width=True):
            with st.spinner("Running M10 Agent Graph on active cases..."):
                from src.agent.graph import graph
                from sqlalchemy import select
                from src.database.models import RecoveryCase
                
                with SessionLocal() as s:
                    cases = s.scalars(select(RecoveryCase).where(RecoveryCase.status.in_(["OPEN", "IN_PROGRESS"]))).all()
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
                    st.rerun()"""

if old_run in content:
    content = content.replace(old_run, new_run)
    with open(app_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Fixed backend invocation in app.py")
else:
    print("Could not find placeholder in app.py")
