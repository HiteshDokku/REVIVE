from typing import Any

"""Orchestrator to hydrate the demo database with real M10 executions."""

import logging
from datetime import UTC, datetime, timedelta

from src.agent.graph import build_graph
from src.agent.state import RecoveryState
from src.database.connection import get_sync_engine, get_sync_session_factory
from src.database.models import AuditEvent, Intervention, Outcome, RecoveryCase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hydrate_demo")


def run_hydration() -> None:
    logger.info("Starting M10 runtime hydration...")

    engine = get_sync_engine()
    SessionLocal = get_sync_session_factory(engine)

    graph = build_graph()

    with SessionLocal() as session:
        # Identify cases that have ALREADY been processed by M10_AGENT
        cases_to_reset = (
            session.query(AuditEvent.case_id)
            .filter(AuditEvent.actor_type == "M10_AGENT")
            .distinct()
            .all()
        )
        case_ids = [r[0] for r in cases_to_reset]

        if case_ids:
            # Revert their status to OPEN so they get picked up again
            session.query(RecoveryCase).filter(RecoveryCase.case_id.in_(case_ids)).update(
                {"status": "OPEN"}, synchronize_session=False
            )

            # Delete ANY interventions, outcomes, or audit events created for these cases
            # since they are still supposed to be "fresh" for this demo
            session.query(Intervention).filter(Intervention.case_id.in_(case_ids)).delete(
                synchronize_session=False
            )
            session.query(Outcome).filter(Outcome.case_id.in_(case_ids)).delete(
                synchronize_session=False
            )
            session.query(AuditEvent).filter(
                AuditEvent.case_id.in_(case_ids), AuditEvent.actor_type == "M10_AGENT"
            ).delete(synchronize_session=False)
            session.commit()

        cases = (
            session.query(RecoveryCase)
            .filter(RecoveryCase.status.in_(["OPEN", "IN_PROGRESS"]))
            .all()
        )  # Process all actionable cases.

        logger.info(f"Found {len(cases)} actionable cases to process.")

        processed = 0
        skipped = 0
        failed = 0
        audit_count = 0

        for case in cases:
            # Removed the skipped block to allow idempotent rerun on the cleared DB.

            try:
                eval_time = case.created_at + timedelta(hours=2)
                initial_state: RecoveryState = {
                    "case_id": str(case.case_id),
                    "customer_id": str(case.customer_id),
                    "current_time": eval_time.isoformat(),
                }

                # We mock datetime in the places that generate new records or evaluate time.
                # We advance time by 1 second per call so that strict inequalities (e.g. i.created_at < now)
                # behave correctly and cooldowns don't stall.
                time_state = {"current": eval_time}

                def mock_now(tz: Any = None) -> datetime:
                    time_state["current"] += timedelta(seconds=1)
                    return time_state["current"]

                from unittest.mock import patch

                with (
                    patch("src.policy.guardrails.datetime") as p_gr,
                    patch("src.agent.tools.payment.datetime") as p_pay,
                    patch("src.agent.tools.communication.datetime") as p_comm,
                ):
                    p_gr.now.side_effect = mock_now
                    p_gr.utcnow.side_effect = mock_now
                    p_pay.now.side_effect = mock_now
                    p_pay.utcnow.side_effect = mock_now
                    p_comm.now.side_effect = mock_now
                    p_comm.utcnow.side_effect = mock_now

                    final_state = graph.invoke(initial_state, {"recursion_limit": 100})

                # Update RecoveryCase
                case.risk_score = final_state.get("risk_score", case.risk_score)
                case.root_cause = final_state.get("root_cause", case.root_cause)
                case.root_cause_confidence = final_state.get(
                    "root_cause_confidence", case.root_cause_confidence
                )
                case.recommended_action = final_state.get(
                    "selected_action", case.recommended_action
                )
                case.expected_recovery = final_state.get(
                    "expected_recovery", case.expected_recovery
                )
                case.expected_net_recovery = final_state.get(
                    "expected_net_recovery", case.expected_net_recovery
                )
                case.decision_confidence = final_state.get(
                    "decision_confidence", case.decision_confidence
                )

                nodes = [a.get("node") for a in final_state.get("audit_context", [])]
                if final_state.get("next_step") == "RECOVERED" or "close_case" in nodes:
                    case.status = "CLOSED"
                elif "escalate" in nodes:
                    case.status = "ESCALATED"
                elif "execute_action" in nodes or "generate_candidate_actions" in nodes:
                    # Do not blindly convert graph control-flow events into business lifecycle states
                    if final_state.get("next_step") != "stop_case" and case.status not in [
                        "CLOSED",
                        "CANCELLED",
                        "ESCALATED",
                    ]:
                        pass  # Preserve domain status

                case.updated_at = datetime.now(UTC)

                # Create AuditEvents
                for idx, entry in enumerate(final_state.get("audit_context", [])):
                    # Embed full state in the final audit entry for the UI to read candidate actions, etc.
                    is_last = idx == len(final_state.get("audit_context", [])) - 1
                    metadata = entry.copy()
                    if is_last:
                        metadata["candidate_actions"] = final_state.get("candidate_actions", [])
                        metadata["recovery_predictions"] = final_state.get(
                            "recovery_predictions", []
                        )
                        metadata["policy_decision"] = final_state.get("policy_decision")

                    audit_event = AuditEvent(
                        case_id=case.case_id,
                        event_type=entry.get("node", "SYSTEM_EVENT"),
                        actor_type="M10_AGENT",
                        event_time=datetime.now(UTC),
                        correlation_id=str(case.case_id),
                        metadata_=metadata,
                        input_snapshot=None,
                        decision=final_state.get("selected_action")
                        if entry.get("node") == "optimize_action"
                        else None,
                        created_at=datetime.now(UTC),
                    )
                    session.add(audit_event)
                    audit_count += 1

                session.commit()
                processed += 1

            except Exception as e:
                session.rollback()
                logger.error(f"Failed processing case {case.case_id}: {e!s}")
                failed += 1

        interventions = session.query(Intervention).count()
        outcomes = session.query(Outcome).count()

        logger.info("Hydration complete.")
        logger.info(f"Cases discovered: {len(cases)}")
        logger.info(f"Cases processed: {processed}")
        logger.info(f"Cases skipped: {skipped}")
        logger.info(f"Cases failed: {failed}")
        logger.info(f"Interventions created: {interventions}")
        logger.info(f"Outcomes created: {outcomes}")
        logger.info(f"Audit events created: {audit_count}")


if __name__ == "__main__":
    run_hydration()
