"""Predict recovery node for the LangGraph agent."""

import uuid
from typing import Any

from src.agent.state import RecoveryState
from src.database.connection import get_sync_session_factory
from src.database.repositories.core import CustomerRepository, RecoveryCaseRepository
from src.faults.injector import get_fault_injector
from src.faults.models import FaultType
from src.models.recovery_propensity import RecoveryPropensityModel

_propensity_model = None


def get_propensity_model() -> RecoveryPropensityModel:
    global _propensity_model
    if _propensity_model is None:
        _propensity_model = RecoveryPropensityModel()
    return _propensity_model


def predict_recovery(state: RecoveryState) -> dict[str, Any]:
    """Score candidate actions using the Recovery Propensity model."""
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

        candidates = state.get("candidate_actions", [])
        predictions = []

        model = get_propensity_model()

        for cand in candidates:
            if not cand.get("is_eligible", False):
                continue

            injector = get_fault_injector()
            if injector.should_inject(FaultType.MODEL_UNAVAILABLE, str(case_id)):
                pred_result = {
                    "recovery_probability": 0.50,
                    "confidence": 0.50,
                    "model_version": "unknown",
                }
            else:
                pred_result = model.predict(
                    case=case,
                    customer=customer,
                    action_type=cand["action_type"],
                    attempt_number=attempt_number,
                    trigger_payment=None,  # In a real implementation we might fetch the triggering payment
                )

            cand_copy = cand.copy()
            cand_copy["recovery_probability"] = pred_result.get("recovery_probability", 0.0)
            cand_copy["confidence"] = pred_result.get("confidence", 1.0)
            cand_copy["model_version"] = pred_result.get("model_version", "1.0")
            predictions.append(cand_copy)

        audit_entry = {
            "node": "predict_recovery",
            "scored_actions": len(predictions),
        }

        current_audit = state.get("audit_context", [])
        return {
            "recovery_predictions": predictions,
            "audit_context": [*current_audit, audit_entry],
        }
