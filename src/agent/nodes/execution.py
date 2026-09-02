"""Execution node for the LangGraph agent."""

import uuid
from typing import Any

from src.agent.state import RecoveryState
from src.agent.tools.base import ToolResult
from src.agent.tools.payment import PaymentActionInput, retry_payment
from src.database.connection import get_sync_session_factory
from src.database.repositories.core import (
    CustomerRepository,
    InterventionRepository,
    RecoveryCaseRepository,
)
from src.simulator.engine import InterventionSimulator

_simulator = None


def get_simulator() -> InterventionSimulator:
    global _simulator
    if _simulator is None:
        _simulator = InterventionSimulator()
    return _simulator


def execute_action(state: RecoveryState) -> dict[str, Any]:
    """Execute the selected action using authorized M9 tools."""
    case_id = uuid.UUID(state["case_id"])
    customer_id = uuid.UUID(state["customer_id"])
    action = state.get("selected_action")
    attempt_number = state.get("attempt_number", 1)

    idempotency_key = f"{case_id}-{attempt_number}-{action}"

    session_factory = get_sync_session_factory()
    with session_factory() as session:
        case = RecoveryCaseRepository(session).get_by_id(case_id)
        customer = CustomerRepository(session).get_by_id(customer_id)

        if not case or not customer:
            raise ValueError("Case or customer not found")

        case.root_cause = state.get("root_cause")

        all_interventions = InterventionRepository(session).list_all()
        past_interventions = [i for i in all_interventions if i.case_id == case_id]

        session_interventions = state.get("session_interventions", [])
        for i_data in session_interventions:
            from src.database.models import Intervention

            past_interventions.append(
                Intervention(
                    case_id=case_id,
                    action_type=i_data["action_type"],
                    created_at=i_data["created_at"],
                    attempt_number=i_data["attempt_number"],
                    cost=i_data["cost"],
                )
            )

        simulator = get_simulator()

        # Route to the appropriate tool based on action string
        result = ToolResult(success=False, message="Action type not supported.")

        if action == "RETRY_LATER":
            input_data = PaymentActionInput(
                case_id=case_id,
                idempotency_key=idempotency_key,
                payment_id=case.source_id,
            )
            result = retry_payment(input_data, case, customer, past_interventions, simulator)
        elif action in ("EMAIL_REMINDER", "SMS_REMINDER"):
            from src.agent.tools.communication import SendMessageInput, send_message

            channel = "EMAIL" if action == "EMAIL_REMINDER" else "SMS"
            input_data_comm = SendMessageInput(
                case_id=case_id,
                customer_id=customer_id,
                idempotency_key=idempotency_key,
                channel=channel,
                message="reminder",
            )
            result = send_message(input_data_comm, case, customer, past_interventions)
        elif action == "NO_ACTION":
            result = ToolResult(success=True, message="No action taken.")
        else:
            # Fallback safe failure
            result = ToolResult(success=False, message=f"Unknown action {action}")

        audit_entry = {
            "node": "execute_action",
            "action": action,
            "success": result.success,
            "message": result.message,
        }

        # Persist created entities to database
        for intervention in result.created_interventions:
            session.add(intervention)
            session_interventions.append(
                {
                    "action_type": intervention.action_type,
                    "created_at": intervention.created_at,
                    "attempt_number": intervention.attempt_number,
                    "cost": intervention.cost,
                }
            )
        for interaction in result.created_interactions:
            session.add(interaction)
        for outcome in result.created_outcomes:
            session.add(outcome)

        session.commit()

        current_audit = state.get("audit_context", [])
        return {
            "execution_result": {
                "success": result.success,
                "message": result.message,
            },
            "audit_context": [*current_audit, audit_entry],
            "session_interventions": session_interventions,
        }
