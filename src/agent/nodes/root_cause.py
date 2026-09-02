"""Diagnose root cause node for the LangGraph agent."""

import uuid
from typing import Any

from src.agent.state import RecoveryState
from src.database.connection import get_sync_session_factory
from src.database.repositories.core import (
    CustomerRepository,
    PaymentRepository,
    RecoveryCaseRepository,
)
from src.faults.injector import get_fault_injector
from src.faults.models import FaultType
from src.features.root_cause_features import RootCauseFeatureExtractor
from src.models.root_cause_inference import RootCauseInferenceService

_root_cause_service = None


def get_root_cause_service() -> RootCauseInferenceService:
    global _root_cause_service
    if _root_cause_service is None:
        _root_cause_service = RootCauseInferenceService()
    return _root_cause_service


def diagnose_root_cause(state: RecoveryState) -> dict[str, Any]:
    """Diagnose the root cause of the payment failure."""
    case_id = uuid.UUID(state["case_id"])
    customer_id = uuid.UUID(state["customer_id"])

    session_factory = get_sync_session_factory()
    with session_factory() as session:
        case = RecoveryCaseRepository(session).get_by_id(case_id)
        customer = CustomerRepository(session).get_by_id(customer_id)

        if not case or not customer:
            raise ValueError("Case or customer not found")

        payments = PaymentRepository(session).list_all()
        cases = RecoveryCaseRepository(session).list_all()

        extractor = RootCauseFeatureExtractor(customers=[customer], payments=payments, cases=cases)
        features = extractor.extract_features(case)

        injector = get_fault_injector()
        if injector.should_inject(FaultType.MODEL_UNAVAILABLE, str(case_id)):
            root_cause = "UNKNOWN"
            confidence = 0.50
            prediction = {"model_name": "unknown", "model_version": "unknown"}
        elif injector.should_inject(FaultType.LLM_UNAVAILABLE, str(case_id)):
            root_cause = "UNKNOWN"
            confidence = 0.50
            prediction = {
                "model_name": "unknown",
                "model_version": "unknown",
                "llm_fallback": "True",
            }
        else:
            service = get_root_cause_service()
            trigger_payment = (
                next((p for p in payments if str(p.payment_id) == str(case.source_id)), None)
                if case.source_type == "payment"
                else None
            )
            fc = trigger_payment.failure_code if trigger_payment else None
            fr = trigger_payment.failure_reason if trigger_payment else None
            prediction = service.diagnose(
                features=features, source_type=case.source_type, failure_code=fc, failure_reason=fr
            )
            root_cause = prediction.get("root_cause", "UNKNOWN")
            confidence = float(prediction.get("confidence", 0.0))

        audit_entry = {
            "node": "diagnose_root_cause",
            "model_name": prediction.get("model_name"),
            "model_version": prediction.get("model_version"),
            "root_cause": root_cause,
            "root_cause_confidence": confidence,
        }

        current_audit = state.get("audit_context", [])
        return {
            "root_cause": str(root_cause),
            "root_cause_confidence": confidence,
            "audit_context": [*current_audit, audit_entry],
        }
