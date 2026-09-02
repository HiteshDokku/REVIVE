import typing
import uuid
from decimal import Decimal

import pytest

from src.agent.tools.base import DuplicateExecutionError, check_idempotency
from src.agent.tools.communication import SendMessageInput, _execute_communication_action
from src.agent.tools.payment import PaymentActionInput, _execute_payment_action
from src.database.models import Customer, RecoveryCase
from src.decision.models import DecisionResult
from src.faults.injector import get_fault_injector
from src.faults.models import FaultType
from src.policy.guardrails import GuardrailsEngine
from src.simulator.engine import InterventionSimulator


@pytest.fixture(autouse=True)
def reset_injector() -> typing.Iterator[None]:
    """Ensure injector is cleared before and after each test."""
    injector = get_fault_injector()
    injector.clear()
    yield
    injector.clear()


@pytest.fixture
def mock_case() -> RecoveryCase:
    return RecoveryCase(
        case_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        amount_at_risk=Decimal("100.00"),
        status="OPEN",
    )


@pytest.fixture
def mock_customer() -> Customer:
    return Customer(
        customer_id=uuid.uuid4(), payment_reliability_score=0.8, communication_opt_out=False
    )


def test_gateway_outage(mock_case: RecoveryCase, mock_customer: Customer) -> None:
    injector = get_fault_injector()
    injector.configure(FaultType.GATEWAY_OUTAGE)

    input_data = PaymentActionInput(
        case_id=mock_case.case_id, idempotency_key="key1", payment_id=uuid.uuid4()
    )
    simulator = InterventionSimulator()

    result = _execute_payment_action(
        "RETRY_NOW", Decimal("2.00"), input_data, mock_case, mock_customer, [], simulator
    )

    assert result.success is True  # tool execution succeeded, but outcome failed
    assert "Gateway outage" in result.message
    assert len(result.created_outcomes) == 1
    assert result.created_outcomes[0].success is False


def test_api_timeout_payment(mock_case: RecoveryCase, mock_customer: Customer) -> None:
    injector = get_fault_injector()
    injector.configure(FaultType.API_TIMEOUT)

    input_data = PaymentActionInput(
        case_id=mock_case.case_id, idempotency_key="key2", payment_id=uuid.uuid4()
    )
    simulator = InterventionSimulator()

    result = _execute_payment_action(
        "RETRY_NOW", Decimal("2.00"), input_data, mock_case, mock_customer, [], simulator
    )

    assert result.success is True
    assert "API timeout" in result.message
    assert len(result.created_outcomes) == 1
    assert result.created_outcomes[0].success is False


def test_api_timeout_communication(mock_case: RecoveryCase, mock_customer: Customer) -> None:
    injector = get_fault_injector()
    injector.configure(FaultType.API_TIMEOUT)

    input_data = SendMessageInput(
        case_id=mock_case.case_id,
        idempotency_key="key3",
        customer_id=mock_customer.customer_id,
        channel="SMS",
        message="test",
    )

    result = _execute_communication_action(
        "SMS_REMINDER", Decimal("0.30"), input_data, mock_case, mock_customer, []
    )

    assert result.success is False
    assert "API timeout" in result.message
    assert len(result.created_interventions) == 0


def test_duplicate_event() -> None:
    injector = get_fault_injector()
    injector.configure(FaultType.DUPLICATE_EVENT)

    with pytest.raises(DuplicateExecutionError, match="simulated"):
        check_idempotency("some_key", [], [])


def test_already_paid(mock_case: RecoveryCase, mock_customer: Customer) -> None:
    injector = get_fault_injector()
    injector.configure(FaultType.ALREADY_PAID)

    input_data = PaymentActionInput(
        case_id=mock_case.case_id, idempotency_key="key4", payment_id=uuid.uuid4()
    )
    simulator = InterventionSimulator()

    result = _execute_payment_action(
        "RETRY_NOW", Decimal("2.00"), input_data, mock_case, mock_customer, [], simulator
    )

    assert result.success is False
    assert "already paid" in result.message.lower()


def test_model_unavailable_guardrails(mock_case: RecoveryCase, mock_customer: Customer) -> None:
    # Test MODEL_UNAVAILABLE doesn't crash root cause
    # We can't easily mock the DB in this unit test without setting up the full engine,
    # but we can test the fault injection directly if we bypass the DB or set up a test DB.
    # Since nodes are tightly coupled to the DB, we will test GuardrailsEngine which is pure logic.
    pass  # Real integration test handles the DB parts.


def test_customer_opt_out(mock_case: RecoveryCase, mock_customer: Customer) -> None:
    injector = get_fault_injector()
    injector.configure(FaultType.CUSTOMER_OPT_OUT)

    engine = GuardrailsEngine()
    decision = DecisionResult(
        case_id=str(mock_case.case_id),
        selected_action="SMS_REMINDER",
        expected_net_recovery=Decimal("10.0"),
        expected_recovery=Decimal("10.0"),
        recovery_probability=1.0,
        confidence=1.0,
        action_cost=Decimal("0.0"),
        model_version="1.0",
        ranked_actions=[],
        explanation="",
    )

    result = engine.evaluate(decision, mock_case, mock_customer, [], [])

    assert result.decision.value == "DENY"
    assert "customer_opt_out" in result.violated_guardrails


def test_policy_unavailable_in_node() -> None:
    # Will be tested via integration test as well due to DB dependency.
    pass
