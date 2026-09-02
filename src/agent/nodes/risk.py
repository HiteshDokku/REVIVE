"""Assess risk node for the LangGraph agent."""

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
from src.features.risk_features import RiskFeatureExtractor
from src.models.inference import RiskInferenceService

_risk_service = None


def get_risk_service() -> RiskInferenceService:
    global _risk_service
    if _risk_service is None:
        _risk_service = RiskInferenceService()
    return _risk_service


def assess_risk(state: RecoveryState) -> dict[str, Any]:
    """Calculate the revenue risk score for the case."""
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

        extractor = RiskFeatureExtractor(customers=[customer], payments=payments, cases=cases)
        features = extractor.extract_features(case)

        injector = get_fault_injector()
        if injector.should_inject(FaultType.MODEL_UNAVAILABLE, str(case_id)):
            score = 0.50  # safe default fallback
            prediction = {"model_name": "unknown", "model_version": "unknown"}
        else:
            service = get_risk_service()
            prediction = service.predict(features)
            score = float(prediction.get("confidence", 0.0))

        audit_entry = {
            "node": "assess_risk",
            "model_name": prediction.get("model_name"),
            "model_version": prediction.get("model_version"),
            "risk_score": score,
        }

        current_audit = state.get("audit_context", [])
        return {
            "risk_score": score,
            "audit_context": [*current_audit, audit_entry],
        }
