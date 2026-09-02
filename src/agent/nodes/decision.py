"""Optimize action node for the LangGraph agent."""

import uuid
from typing import Any

from src.agent.state import RecoveryState
from src.database.connection import get_sync_session_factory
from src.database.repositories.core import CustomerRepository, RecoveryCaseRepository
from src.decision.policy import ExpectedValuePolicy

_ev_policy = None


def get_ev_policy() -> ExpectedValuePolicy:
    global _ev_policy
    if _ev_policy is None:
        from src.agent.nodes.propensity import get_propensity_model

        _ev_policy = ExpectedValuePolicy(propensity_model=get_propensity_model())
    return _ev_policy


def optimize_action(state: RecoveryState) -> dict[str, Any]:
    """Select the optimal action using the Economic Decision Engine."""
    case_id = uuid.UUID(state["case_id"])
    customer_id = uuid.UUID(state["customer_id"])
    attempt_number = state.get("attempt_number", 1)

    session_factory = get_sync_session_factory()
    with session_factory() as session:
        case = RecoveryCaseRepository(session).get_by_id(case_id)
        customer = CustomerRepository(session).get_by_id(customer_id)

        if not case or not customer:
            raise ValueError("Case or customer not found")

        case.root_cause = state.get("root_cause")

        policy = get_ev_policy()
        decision = policy.evaluate(
            case=case,
            customer=customer,
            attempt_number=attempt_number,
        )

        audit_entry = {
            "node": "optimize_action",
            "selected_action": decision.selected_action,
            "expected_net_recovery": float(decision.expected_net_recovery),
        }

        current_audit = state.get("audit_context", [])
        return {
            "selected_action": decision.selected_action,
            "expected_recovery": float(decision.expected_recovery),
            "expected_net_recovery": float(decision.expected_net_recovery),
            "decision_confidence": decision.confidence,
            "audit_context": [*current_audit, audit_entry],
        }
