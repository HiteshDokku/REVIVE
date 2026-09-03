import sys

sys.stdout.reconfigure(encoding="utf-8")
from sqlalchemy import String, cast, create_engine, func
from sqlalchemy.orm import sessionmaker

engine = create_engine("sqlite:///data/revive_dev.db")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = SessionLocal()
from src.database.models import AuditEvent, Intervention, RecoveryCase

total_cases = session.query(func.count(RecoveryCase.case_id)).scalar()
actionable_cases = (
    session.query(func.count(RecoveryCase.case_id))
    .filter(RecoveryCase.status.in_(["OPEN", "IN_PROGRESS"]))
    .scalar()
)
policy_evals = (
    session.query(func.count(AuditEvent.event_id))
    .filter(AuditEvent.event_type == "policy_check")
    .scalar()
)
deny_decisions = (
    session.query(func.count(AuditEvent.event_id))
    .filter(AuditEvent.event_type == "policy_check")
    .filter(cast(AuditEvent.metadata_, String).like('%"policy_decision": "DENY"%'))
    .scalar()
)
allow_decisions = (
    session.query(func.count(AuditEvent.event_id))
    .filter(AuditEvent.event_type == "policy_check")
    .filter(cast(AuditEvent.metadata_, String).like('%"policy_decision": "ALLOW"%'))
    .scalar()
)
executed_interventions = (
    session.query(func.count(Intervention.intervention_id))
    .filter(Intervention.status == "COMPLETED")
    .scalar()
)
blocked_interventions = (
    session.query(func.count(Intervention.intervention_id))
    .filter(Intervention.status == "BLOCKED")
    .scalar()
)

print(f"Total cases: {total_cases}")
print(f"Actionable cases: {actionable_cases}")
print(f"Policy evaluations: {policy_evals}")
print(f"ALLOW decisions: {allow_decisions}")
print(f"DENY decisions: {deny_decisions}")
print(f"Executed interventions: {executed_interventions}")
print(f"Blocked interventions: {blocked_interventions}")
