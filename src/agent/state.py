"""Agent State definition for the LangGraph orchestrator."""

from typing import Any, TypedDict


class RecoveryState(TypedDict, total=False):
    """The state dictionary for the REVIVE LangGraph agent."""

    case_id: str
    customer_id: str
    source_type: str
    source_id: str
    amount_at_risk: float
    customer_context: dict[str, Any]
    transaction_context: dict[str, Any]
    risk_score: float
    root_cause: str
    root_cause_confidence: float
    candidate_actions: list[dict[str, Any]]
    recovery_predictions: list[dict[str, Any]]
    selected_action: str
    expected_recovery: float
    expected_net_recovery: float
    decision_confidence: float
    policy_decision: str
    policy_reasons: list[str]
    intervention_id: str
    execution_result: dict[str, Any]
    outcome: dict[str, Any]
    attempt_number: int
    communication_count: int
    retry_count: int
    next_step: str
    stop_reason: str
    audit_context: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    current_time: str  # ISO formatted datetime string for deterministic evaluation
    session_interventions: list[dict[str, Any]]
