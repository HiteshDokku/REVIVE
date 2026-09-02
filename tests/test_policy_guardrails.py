"""Tests for the Policy and Guardrails layer (Milestone 8)."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.database.models import Customer, Intervention, RecoveryCase
from src.decision.models import DecisionResult
from src.policy.config import GuardrailConfig
from src.policy.guardrails import GuardrailsEngine
from src.policy.models import PolicyDecisionStatus


@pytest.fixture
def base_time() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def mock_case(base_time: datetime) -> RecoveryCase:
    return RecoveryCase(
        case_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        status="OPEN",
        created_at=base_time - timedelta(days=2),
        amount_at_risk=Decimal("500.00"),
    )


@pytest.fixture
def mock_customer() -> Customer:
    return Customer(customer_id=uuid.uuid4(), communication_opt_out=False)


@pytest.fixture
def mock_decision(mock_case: RecoveryCase) -> DecisionResult:
    return DecisionResult(
        case_id=str(mock_case.case_id),
        selected_action="EMAIL_REMINDER",
        expected_net_recovery=Decimal("150.00"),
        expected_recovery=Decimal("150.05"),
        recovery_probability=0.3,
        confidence=0.9,
        action_cost=Decimal("0.05"),
        model_version="1.0",
        ranked_actions=[],
        explanation="Test",
    )


@pytest.fixture
def engine() -> GuardrailsEngine:
    return GuardrailsEngine(
        config=GuardrailConfig(
            max_payment_retries=2,
            min_retry_cooldown_hours=12,
            max_recovery_window_days=14,
            max_customer_contacts=3,
            min_contact_cooldown_hours=24,
            high_value_threshold=Decimal("100000.00"),
            min_expected_net_recovery=Decimal("50.00"),
        )
    )


def test_positive_path_allow(
    engine: GuardrailsEngine,
    mock_case: RecoveryCase,
    mock_customer: Customer,
    mock_decision: DecisionResult,
    base_time: datetime,
) -> None:
    """Valid action -> ALLOW"""
    result = engine.evaluate(
        mock_decision, mock_case, mock_customer, [], [], current_time=base_time
    )
    assert result.decision == PolicyDecisionStatus.ALLOW
    assert result.action_type == "EMAIL_REMINDER"


def test_positive_path_retry_allow(
    engine: GuardrailsEngine,
    mock_case: RecoveryCase,
    mock_customer: Customer,
    mock_decision: DecisionResult,
    base_time: datetime,
) -> None:
    """Valid retry action -> ALLOW"""
    mock_decision.selected_action = "RETRY_LATER"
    result = engine.evaluate(
        mock_decision, mock_case, mock_customer, [], [], current_time=base_time
    )
    assert result.decision == PolicyDecisionStatus.ALLOW


def test_negative_path_retry_limit_exceeded(
    engine: GuardrailsEngine,
    mock_case: RecoveryCase,
    mock_customer: Customer,
    mock_decision: DecisionResult,
    base_time: datetime,
) -> None:
    """Retry limit exceeded -> DENY"""
    mock_decision.selected_action = "RETRY_LATER"

    interventions = [
        Intervention(
            action_type="RETRY_LATER", status="COMPLETED", created_at=base_time - timedelta(days=2)
        ),
        Intervention(
            action_type="RETRY_LATER", status="COMPLETED", created_at=base_time - timedelta(days=1)
        ),
    ]

    result = engine.evaluate(
        mock_decision, mock_case, mock_customer, interventions, [], current_time=base_time
    )
    assert result.decision == PolicyDecisionStatus.DENY
    assert "retry_limit" in result.violated_guardrails


def test_negative_path_contact_limit_exceeded(
    engine: GuardrailsEngine,
    mock_case: RecoveryCase,
    mock_customer: Customer,
    mock_decision: DecisionResult,
    base_time: datetime,
) -> None:
    """Contact limit exceeded -> DENY"""
    interventions = [
        Intervention(action_type="EMAIL_REMINDER", created_at=base_time - timedelta(days=4)),
        Intervention(action_type="SMS_REMINDER", created_at=base_time - timedelta(days=3)),
        Intervention(action_type="EMAIL_REMINDER", created_at=base_time - timedelta(days=2)),
    ]
    result = engine.evaluate(
        mock_decision, mock_case, mock_customer, interventions, [], current_time=base_time
    )
    assert result.decision == PolicyDecisionStatus.DENY
    assert "contact_limit" in result.violated_guardrails


def test_negative_path_contact_cooldown(
    engine: GuardrailsEngine,
    mock_case: RecoveryCase,
    mock_customer: Customer,
    mock_decision: DecisionResult,
    base_time: datetime,
) -> None:
    """Contact cooldown active -> DENY"""
    interventions = [
        Intervention(action_type="EMAIL_REMINDER", created_at=base_time - timedelta(hours=12))
    ]
    result = engine.evaluate(
        mock_decision, mock_case, mock_customer, interventions, [], current_time=base_time
    )
    assert result.decision == PolicyDecisionStatus.DENY
    assert "cooldown" in result.violated_guardrails


def test_negative_path_retry_cooldown(
    engine: GuardrailsEngine,
    mock_case: RecoveryCase,
    mock_customer: Customer,
    mock_decision: DecisionResult,
    base_time: datetime,
) -> None:
    """Retry cooldown active -> DENY"""
    mock_decision.selected_action = "RETRY_LATER"
    interventions = [
        Intervention(
            action_type="RETRY_LATER", status="COMPLETED", created_at=base_time - timedelta(hours=6)
        )
    ]
    result = engine.evaluate(
        mock_decision, mock_case, mock_customer, interventions, [], current_time=base_time
    )
    assert result.decision == PolicyDecisionStatus.DENY
    assert "cooldown" in result.violated_guardrails


def test_negative_path_recovery_window_expired(
    engine: GuardrailsEngine,
    mock_case: RecoveryCase,
    mock_customer: Customer,
    mock_decision: DecisionResult,
    base_time: datetime,
) -> None:
    """Recovery window expired -> DENY"""
    # 15 days ago, max is 14
    mock_case.created_at = base_time - timedelta(days=15)
    result = engine.evaluate(
        mock_decision, mock_case, mock_customer, [], [], current_time=base_time
    )
    assert result.decision == PolicyDecisionStatus.DENY
    assert "recovery_window" in result.violated_guardrails


def test_negative_path_customer_opt_out(
    engine: GuardrailsEngine,
    mock_case: RecoveryCase,
    mock_customer: Customer,
    mock_decision: DecisionResult,
    base_time: datetime,
) -> None:
    """Customer opted out -> DENY communication"""
    mock_customer.communication_opt_out = True
    result = engine.evaluate(
        mock_decision, mock_case, mock_customer, [], [], current_time=base_time
    )
    assert result.decision == PolicyDecisionStatus.DENY
    assert "customer_opt_out" in result.violated_guardrails

    # Opt-out shouldn't block financial actions (retries)
    mock_decision.selected_action = "RETRY_LATER"
    result = engine.evaluate(
        mock_decision, mock_case, mock_customer, [], [], current_time=base_time
    )
    assert result.decision == PolicyDecisionStatus.ALLOW


def test_negative_path_already_recovered(
    engine: GuardrailsEngine,
    mock_case: RecoveryCase,
    mock_customer: Customer,
    mock_decision: DecisionResult,
    base_time: datetime,
) -> None:
    """Already recovered -> DENY (Stop Rule)"""
    mock_case.status = "RECOVERED"
    result = engine.evaluate(
        mock_decision, mock_case, mock_customer, [], [], current_time=base_time
    )
    assert result.decision == PolicyDecisionStatus.DENY
    assert "already_resolved" in result.violated_guardrails


def test_negative_path_economic_threshold(
    engine: GuardrailsEngine,
    mock_case: RecoveryCase,
    mock_customer: Customer,
    mock_decision: DecisionResult,
    base_time: datetime,
) -> None:
    """Insufficient economic value -> DENY"""
    mock_decision.expected_net_recovery = Decimal("10.00")  # min is 50.00
    result = engine.evaluate(
        mock_decision, mock_case, mock_customer, [], [], current_time=base_time
    )
    assert result.decision == PolicyDecisionStatus.DENY
    assert "economic_threshold" in result.violated_guardrails


def test_negative_path_high_value_escalation(
    engine: GuardrailsEngine,
    mock_case: RecoveryCase,
    mock_customer: Customer,
    mock_decision: DecisionResult,
    base_time: datetime,
) -> None:
    """High value case -> ESCALATE"""
    mock_case.amount_at_risk = Decimal("150000.00")  # threshold is 100,000

    # Needs to pass economic threshold first to reach the escalation check if we want,
    # actually precedence puts escalation BEFORE economic threshold.
    mock_decision.expected_net_recovery = Decimal("100.00")

    result = engine.evaluate(
        mock_decision, mock_case, mock_customer, [], [], current_time=base_time
    )
    assert result.decision == PolicyDecisionStatus.ESCALATE
    assert "high_value_escalation" in result.violated_guardrails


def test_boundary_retry_limit(
    engine: GuardrailsEngine,
    mock_case: RecoveryCase,
    mock_customer: Customer,
    mock_decision: DecisionResult,
    base_time: datetime,
) -> None:
    """Exactly at retry limit -> DENY. Below limit -> ALLOW."""
    mock_decision.selected_action = "RETRY_LATER"

    # 1 retry = ALLOW
    interventions = [
        Intervention(
            action_type="RETRY_LATER", status="COMPLETED", created_at=base_time - timedelta(days=2)
        )
    ]
    res = engine.evaluate(
        mock_decision, mock_case, mock_customer, interventions, [], current_time=base_time
    )
    assert res.decision == PolicyDecisionStatus.ALLOW

    # 2 retries = DENY
    interventions.append(
        Intervention(
            action_type="RETRY_LATER", status="COMPLETED", created_at=base_time - timedelta(days=1)
        )
    )
    res2 = engine.evaluate(
        mock_decision, mock_case, mock_customer, interventions, [], current_time=base_time
    )
    assert res2.decision == PolicyDecisionStatus.DENY


def test_boundary_cooldown(
    engine: GuardrailsEngine,
    mock_case: RecoveryCase,
    mock_customer: Customer,
    mock_decision: DecisionResult,
    base_time: datetime,
) -> None:
    """Exactly at cooldown limit. Cooldown is 12h for retries."""
    mock_decision.selected_action = "RETRY_LATER"

    # Exactly 11h 59m ago = DENY
    interventions = [
        Intervention(
            action_type="RETRY_LATER",
            status="COMPLETED",
            created_at=base_time - timedelta(hours=11, minutes=59),
        )
    ]
    res = engine.evaluate(
        mock_decision, mock_case, mock_customer, interventions, [], current_time=base_time
    )
    assert res.decision == PolicyDecisionStatus.DENY

    # Exactly 12h 1m ago = ALLOW
    interventions2 = [
        Intervention(
            action_type="RETRY_LATER",
            status="COMPLETED",
            created_at=base_time - timedelta(hours=12, minutes=1),
        )
    ]
    res2 = engine.evaluate(
        mock_decision, mock_case, mock_customer, interventions2, [], current_time=base_time
    )
    assert res2.decision == PolicyDecisionStatus.ALLOW


def test_security_leakage(
    engine: GuardrailsEngine,
    mock_case: RecoveryCase,
    mock_customer: Customer,
    mock_decision: DecisionResult,
    base_time: datetime,
) -> None:
    """Ensure future events are not considered in policy evaluation."""
    # Future contact (e.g. leaked from outcome generator)
    interventions = [
        Intervention(action_type="EMAIL_REMINDER", created_at=base_time + timedelta(hours=1))
    ]
    # If the policy leaks future events, it would trigger a cooldown DENY.
    # It must ignore them and return ALLOW.
    res = engine.evaluate(
        mock_decision, mock_case, mock_customer, interventions, [], current_time=base_time
    )
    assert res.decision == PolicyDecisionStatus.ALLOW


def test_security_missing_data(
    engine: GuardrailsEngine,
    mock_case: RecoveryCase,
    mock_customer: Customer,
    mock_decision: DecisionResult,
    base_time: datetime,
) -> None:
    """Missing mandatory data falls back to safe DENY."""
    mock_decision.selected_action = ""  # Using empty string to trigger failure path
    res = engine.evaluate(mock_decision, mock_case, mock_customer, [], [], current_time=base_time)
    assert res.decision == PolicyDecisionStatus.DENY
    assert "fail_safe" in res.violated_guardrails


def test_idempotency(
    engine: GuardrailsEngine,
    mock_case: RecoveryCase,
    mock_customer: Customer,
    mock_decision: DecisionResult,
    base_time: datetime,
) -> None:
    """Repeated calls to the policy engine yield the same result."""
    res1 = engine.evaluate(mock_decision, mock_case, mock_customer, [], [], current_time=base_time)
    res2 = engine.evaluate(mock_decision, mock_case, mock_customer, [], [], current_time=base_time)
    assert res1.model_dump() == res2.model_dump()
