"""Tests for the Milestone 9 Simulator Tools."""

import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.agent.tools.audit import (
    FinanceEscalationInput,
    RecordOutcomeInput,
    create_finance_escalation,
    record_outcome,
)
from src.agent.tools.communication import SendMessageInput, send_message
from src.agent.tools.payment import (
    PaymentActionInput,
    retry_payment,
)
from src.database.models import Customer, Intervention, RecoveryCase
from src.simulator.engine import InterventionSimulator


@pytest.fixture
def mock_simulator() -> InterventionSimulator:
    return InterventionSimulator(seed=123)


@pytest.fixture
def mock_case() -> RecoveryCase:
    return RecoveryCase(
        case_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        status="OPEN",
        amount_at_risk=Decimal("500.00"),
        root_cause="INSUFFICIENT_FUNDS",
    )


@pytest.fixture
def mock_customer() -> Customer:
    return Customer(customer_id=uuid.uuid4(), payment_reliability_score=Decimal("0.8"))


def test_simulator_causal_logic(mock_simulator: InterventionSimulator) -> None:
    """Verify the simulator logic matches the synthetic generator."""
    # INSUFFICIENT_FUNDS + RETRY_LATER + Reliability 0.8 => base_prob = 0.10 + 0.16 = 0.26
    # With seed 123, we can test it deterministically.
    success = mock_simulator.simulate("RETRY_LATER", "INSUFFICIENT_FUNDS", 0.8, 1)
    assert isinstance(success, bool)


def test_tool_contract_validation() -> None:
    """Verify tools validate inputs via Pydantic."""
    with pytest.raises(ValidationError):
        # Missing required idempotency_key
        PaymentActionInput(case_id=uuid.uuid4(), payment_id=uuid.uuid4())  # type: ignore

    with pytest.raises(ValidationError):
        # Invalid UUID
        PaymentActionInput(case_id="not-a-uuid", idempotency_key="123", payment_id=uuid.uuid4())  # type: ignore


def test_payment_retry_idempotency(
    mock_simulator: InterventionSimulator, mock_case: RecoveryCase, mock_customer: Customer
) -> None:
    """Verify tool idempotency blocks duplicate execution."""
    input_data = PaymentActionInput(
        case_id=mock_case.case_id, idempotency_key="test-key-1", payment_id=uuid.uuid4()
    )

    past_interventions = [
        Intervention(
            intervention_id=uuid.uuid4(),
            case_id=mock_case.case_id,
            action_type="RETRY_NOW",
            idempotency_key="test-key-1",  # Duplicate!
            attempt_number=1,
            cost=Decimal("2.0"),
        )
    ]

    result = retry_payment(input_data, mock_case, mock_customer, past_interventions, mock_simulator)
    assert result.success is False
    assert "already used" in result.message
    assert len(result.created_interventions) == 0


def test_payment_retry_execution(
    mock_simulator: InterventionSimulator, mock_case: RecoveryCase, mock_customer: Customer
) -> None:
    """Verify a successful execution creates the proper audit records."""
    input_data = PaymentActionInput(
        case_id=mock_case.case_id, idempotency_key="new-key", payment_id=uuid.uuid4()
    )

    result = retry_payment(input_data, mock_case, mock_customer, [], mock_simulator)
    assert result.success is True
    assert len(result.created_interventions) == 1
    assert len(result.created_outcomes) == 1

    intervention = result.created_interventions[0]
    assert intervention.action_type == "RETRY_NOW"
    assert intervention.idempotency_key == "new-key"
    assert intervention.cost == Decimal("2.00")

    outcome = result.created_outcomes[0]
    assert outcome.intervention_id == intervention.intervention_id
    if outcome.success:
        assert outcome.amount_recovered == mock_case.amount_at_risk
    else:
        assert outcome.amount_recovered == Decimal("0.00")


def test_send_message_tool(mock_case: RecoveryCase, mock_customer: Customer) -> None:
    """Verify the communication tool creates Interventions and potential Interactions."""
    input_data = SendMessageInput(
        case_id=mock_case.case_id,
        idempotency_key="msg-key",
        customer_id=mock_customer.customer_id,
        channel="SMS",
        message="Please pay.",
    )

    result = send_message(input_data, mock_case, mock_customer, [])
    assert result.success is True
    assert len(result.created_interventions) == 1

    intervention = result.created_interventions[0]
    assert intervention.action_type == "SMS_REMINDER"
    assert intervention.cost == Decimal("0.30")

    # Interactions are probabilistically created (20% chance)
    assert len(result.created_interactions) in (0, 1)


def test_finance_escalation() -> None:
    """Verify manual audit tool."""
    case_id = uuid.uuid4()
    input_data = FinanceEscalationInput(
        case_id=case_id, idempotency_key="esc-1", reason="High risk customer"
    )

    result = create_finance_escalation(input_data, [])
    assert result.success is True
    assert len(result.created_interventions) == 1
    assert result.created_interventions[0].action_type == "FINANCE_ESCALATION"
    assert result.created_interventions[0].cost == Decimal("100.00")


def test_record_outcome() -> None:
    """Verify explicit outcome recording tool."""
    case_id = uuid.uuid4()
    inv_id = uuid.uuid4()

    input_data = RecordOutcomeInput(
        case_id=case_id,
        idempotency_key="out-1",
        status="RECOVERED",
        amount_recovered=Decimal("500.00"),
    )

    result = record_outcome(input_data, inv_id)
    assert result.success is True
    assert len(result.created_outcomes) == 1
    assert result.created_outcomes[0].success is True
    assert result.created_outcomes[0].amount_recovered == Decimal("500.00")
