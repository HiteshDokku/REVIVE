"""Loader node for the LangGraph agent."""

import uuid
from typing import Any

from src.agent.state import RecoveryState
from src.database.connection import get_sync_session_factory
from src.database.repositories.core import CustomerRepository, RecoveryCaseRepository


def load_case(state: RecoveryState) -> dict[str, Any]:
    """Load case and customer context into the state."""
    case_id_str = state["case_id"]
    case_id = uuid.UUID(case_id_str)

    session_factory = get_sync_session_factory()
    with session_factory() as session:
        case = RecoveryCaseRepository(session).get_by_id(case_id)
        if not case:
            raise ValueError(f"Case {case_id} not found.")

        customer = CustomerRepository(session).get_by_id(case.customer_id)
        if not customer:
            raise ValueError(f"Customer {case.customer_id} not found.")

        return {
            "customer_id": str(customer.customer_id),
            "amount_at_risk": float(case.amount_at_risk),
            "source_type": case.source_type,
            "source_id": str(case.source_id),
            "customer_context": {
                "customer_type": customer.customer_type,
                "payment_reliability_score": float(customer.payment_reliability_score)
                if customer.payment_reliability_score
                else 0.0,
                "communication_opt_out": customer.communication_opt_out,
                "preferred_channel": customer.preferred_channel,
            },
            "transaction_context": {
                "status": case.status,
                "created_at": case.created_at.isoformat() if case.created_at else None,
            },
            "attempt_number": 1,
            "communication_count": 0,
            "retry_count": 0,
            "audit_context": [
                *state.get("audit_context", []),
                {"node": "load_case", "case_id": str(case_id)},
            ],
            "errors": [],
        }
