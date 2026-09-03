from sqlalchemy import String, cast, create_engine, select
from sqlalchemy.orm import Session

from src.database.models import AuditEvent

engine = create_engine("sqlite:///data/revive_dev.db")
with Session(engine) as session:
    stmt = select(AuditEvent).where(
        AuditEvent.event_type == "policy_check",
        cast(AuditEvent.metadata_, String).like('%"policy_decision": "DENY"%'),
    )
    count = len(session.scalars(stmt).all())
    print("JSON query count:", count)
