"""Generate candidate actions node for the LangGraph agent."""

import uuid
from typing import Any

from src.agent.state import RecoveryState
from src.database.connection import get_sync_session_factory
from src.database.repositories.core import CustomerRepository, RecoveryCaseRepository
from src.decision.candidates import CandidateActionGenerator


def generate_candidate_actions(state: RecoveryState) -> dict[str, Any]:
    """Generate candidate actions for the current case."""
    case_id = uuid.UUID(state["case_id"])
    customer_id = uuid.UUID(state["customer_id"])

    session_factory = get_sync_session_factory()
    with session_factory() as session:
        case = RecoveryCaseRepository(session).get_by_id(case_id)
        customer = CustomerRepository(session).get_by_id(customer_id)

        if not case or not customer:
            raise ValueError("Case or customer not found")

        # Update case with risk and root cause found by previous nodes
        # so the generator has access to them
        case.root_cause = state.get("root_cause")

        generator = CandidateActionGenerator()
        candidates = generator.generate(case, customer)

        # Serialize candidate actions
        serialized_candidates = []
        for c in candidates:
            serialized_candidates.append(
                {
                    "action_type": c.action_type,
                    "action_cost": float(c.action_cost),
                    "recoverable_amount": float(c.recoverable_amount),
                    "is_eligible": c.is_eligible,
                    "ineligibility_reason": c.ineligibility_reason,
                }
            )

        audit_entry = {
            "node": "generate_candidate_actions",
            "candidate_count": len(serialized_candidates),
        }

        current_audit = state.get("audit_context", [])
        return {
            "candidate_actions": serialized_candidates,
            "audit_context": [*current_audit, audit_entry],
        }
