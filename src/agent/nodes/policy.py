"""Policy check node for the LangGraph agent."""

import uuid
from decimal import Decimal
from typing import Any

from src.agent.state import RecoveryState
from src.database.connection import get_sync_session_factory
from src.database.repositories.core import (
    CustomerRepository,
    InteractionRepository,
    InterventionRepository,
    RecoveryCaseRepository,
)
from src.decision.models import DecisionResult
from src.faults.injector import get_fault_injector
from src.faults.models import FaultType
from src.policy.guardrails import GuardrailsEngine

_guardrails = None


def get_guardrails() -> GuardrailsEngine:
    global _guardrails
    if _guardrails is None:
        _guardrails = GuardrailsEngine()
    return _guardrails


def policy_check(state: RecoveryState) -> dict[str, Any]:
    """Evaluate the selected action against Guardrails."""
    case_id = uuid.UUID(state["case_id"])
    customer_id = uuid.UUID(state["customer_id"])

    session_factory = get_sync_session_factory()
    with session_factory() as session:
        case = RecoveryCaseRepository(session).get_by_id(case_id)
        customer = CustomerRepository(session).get_by_id(customer_id)

        if not case or not customer:
            raise ValueError("Case or customer not found")

        case.root_cause = state.get("root_cause")

        # In a real app we'd scope queries, doing list_all() then filter matches the synthetic dataset scale
        all_interventions = InterventionRepository(session).list_all()
        all_interactions = InteractionRepository(session).list_all()

        case_interventions = [i for i in all_interventions if i.case_id == case_id]
        customer_interactions = [i for i in all_interactions if i.customer_id == customer_id]

        session_interventions = state.get("session_interventions", [])
        for i_data in session_interventions:
            from src.database.models import Intervention

            case_interventions.append(
                Intervention(
                    case_id=case_id,
                    action_type=i_data["action_type"],
                    created_at=i_data["created_at"],
                    attempt_number=i_data["attempt_number"],
                    cost=i_data["cost"],
                )
            )

        # Reconstruct DecisionResult
        decision = DecisionResult(
            case_id=str(case_id),
            selected_action=state.get("selected_action", ""),
            expected_net_recovery=Decimal(str(state.get("expected_net_recovery", 0.0))),
            expected_recovery=Decimal(str(state.get("expected_recovery", 0.0))),
            recovery_probability=0.0,
            confidence=state.get("decision_confidence", 1.0),
            action_cost=Decimal("0.0"),
            model_version="1.0",
            ranked_actions=[],
            explanation="",
        )

        injector = get_fault_injector()
        if injector.should_inject(FaultType.POLICY_UNAVAILABLE, str(case_id)):
            policy_decision = "DENY"
            violated_guardrails = ["POLICY_UNAVAILABLE_DEFAULT_DENY"]
        else:
            engine = get_guardrails()
            result = engine.evaluate(
                decision=decision,
                case=case,
                customer=customer,
                interventions=case_interventions,
                interactions=customer_interactions,
            )
            policy_decision = result.decision.value
            violated_guardrails = result.violated_guardrails

        audit_entry = {
            "node": "policy_check",
            "policy_decision": policy_decision,
            "violated_guardrails": violated_guardrails,
        }

        current_audit = state.get("audit_context", [])
        return {
            "policy_decision": policy_decision,
            "policy_reasons": violated_guardrails,
            "audit_context": [*current_audit, audit_entry],
        }
