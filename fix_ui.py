filepath = r"src/api/services/ui_service.py"
with open(filepath, encoding="utf-8") as f:
    content = f.read()
old_code = """    intervention = session.scalars(intervention_stmt).first()

    # Get the latest audit event"""
new_code = """    intervention = session.scalars(intervention_stmt).first()

    # Get outcome
    from src.database.models import Outcome
    outcome_stmt = (
        select(Outcome)
        .where(Outcome.case_id == case_uuid)
        .order_by(desc(Outcome.created_at))
        .limit(1)
    )
    outcome = session.scalars(outcome_stmt).first()

    # Get the latest audit event"""
content = content.replace(old_code, new_code)
old_code_2 = """            "stop_reason": case.stop_reason,
            "created_at": case.created_at,
            "candidate_actions": candidate_actions,
        },"""
new_code_2 = """            "stop_reason": case.stop_reason,
            "created_at": case.created_at,
            "candidate_actions": candidate_actions,
            "amount_recovered": outcome.amount_recovered if outcome else None,
        },"""
content = content.replace(old_code_2, new_code_2)
with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed ui_service.py")
