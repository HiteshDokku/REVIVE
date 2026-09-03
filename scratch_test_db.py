from sqlalchemy import text

from src.database.connection import get_sync_session_factory


def run_queries():
    SessionLocal = get_sync_session_factory()
    with SessionLocal() as session:
        # Total RecoveryCases
        total_cases = session.execute(text("SELECT COUNT(*) FROM recovery_cases")).scalar()

        # Actionable RecoveryCases
        case_statuses = session.execute(
            text("SELECT status, COUNT(*) FROM recovery_cases GROUP BY status")
        ).fetchall()

        # Total policy_check AuditEvents
        total_policy_audits = session.execute(
            text("SELECT COUNT(*) FROM audit_events WHERE event_type = 'policy_check'")
        ).scalar()

        # Details of policy_check audits
        policy_audits_details = session.execute(
            text(
                "SELECT metadata, COUNT(*) FROM audit_events WHERE event_type = 'policy_check' GROUP BY metadata"
            )
        ).fetchall()

        # Total Intervention records
        total_interventions = session.execute(text("SELECT COUNT(*) FROM interventions")).scalar()

        # Group Interventions by status
        intervention_statuses = session.execute(
            text("SELECT status, COUNT(*) FROM interventions GROUP BY status")
        ).fetchall()

        # Group Interventions by policy_decision
        policy_decision_counts = session.execute(
            text("SELECT policy_decision, COUNT(*) FROM interventions GROUP BY policy_decision")
        ).fetchall()

        # Successful Outcomes
        successful_outcomes = session.execute(
            text("SELECT COUNT(*) FROM outcomes WHERE success = 1")
        ).scalar()

        print(f"Total RecoveryCases: {total_cases}")
        print(f"Case Statuses: {case_statuses}")
        print(f"Total policy_check AuditEvents: {total_policy_audits}")
        print(f"Policy Audit Details: {policy_audits_details}")
        print(f"Total Interventions: {total_interventions}")
        print(f"Intervention Statuses: {intervention_statuses}")
        print(f"Intervention Policy Decisions: {policy_decision_counts}")
        print(f"Successful Outcomes: {successful_outcomes}")

        # Inspect a few policy_check records
        print("\n--- Sample Audit Events ---")
        samples = session.execute(
            text("SELECT policy_result FROM audit_events WHERE event_type = 'policy_check' LIMIT 5")
        ).fetchall()
        for s in samples:
            print(s)

        print("\n--- Sample Interventions ---")
        samples = session.execute(
            text("SELECT policy_decision, status, action_type FROM interventions LIMIT 5")
        ).fetchall()
        for s in samples:
            print(s)


if __name__ == "__main__":
    run_queries()
