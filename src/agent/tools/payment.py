"""Simulated payment execution tools."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel

from src.agent.tools.base import (
    BaseToolInput,
    DuplicateExecutionError,
    ToolResult,
    check_idempotency,
)
from src.database.models import Customer, Intervention, Outcome, RecoveryCase
from src.faults.injector import get_fault_injector
from src.faults.models import FaultType
from src.simulator.engine import InterventionSimulator


class GetPaymentStatusInput(BaseModel):
    payment_id: uuid.UUID


class PaymentActionInput(BaseToolInput):
    payment_id: uuid.UUID


class ScheduleRetryInput(PaymentActionInput):
    scheduled_at: datetime


def get_payment_status(case: RecoveryCase) -> str:
    """Read-only tool to get the current status of the payment/case."""
    # Since we simulate everything based on the case, we just return the case status.
    return case.status


def _execute_payment_action(
    action_type: str,
    cost: Decimal,
    input_data: PaymentActionInput,
    case: RecoveryCase,
    customer: Customer,
    past_interventions: list[Intervention],
    simulator: InterventionSimulator,
    scheduled_at: datetime | None = None,
) -> ToolResult:
    """Shared logic for executing simulated payment actions."""
    try:
        check_idempotency(input_data.idempotency_key, past_interventions, [])
    except DuplicateExecutionError as e:
        return ToolResult(success=False, message=str(e))

    now = datetime.now(UTC)
    exec_time = scheduled_at or now

    # Check for ALREADY_PAID fault before execution
    injector = get_fault_injector()
    if injector.should_inject(FaultType.ALREADY_PAID, str(case.case_id)):
        return ToolResult(success=False, message="Payment already paid; intervention blocked.")

    # Calculate attempt number
    attempt_number = sum(1 for i in past_interventions if i.action_type == action_type) + 1

    # Check for GATEWAY_OUTAGE or API_TIMEOUT
    if injector.should_inject(FaultType.GATEWAY_OUTAGE, str(case.case_id)):
        success = False
        message = "Gateway outage: execution failed safely."
    elif injector.should_inject(FaultType.API_TIMEOUT, str(case.case_id)):
        success = False
        message = "API timeout: execution state unknown/retryable."
    else:
        # Simulate outcome
        success = simulator.simulate(
            action_type=action_type,
            failure_reason=case.root_cause or "UNKNOWN",
            reliability_score=float(customer.payment_reliability_score or 0.0),
            attempt_number=attempt_number,
        )
        message = f"Action {action_type} executed. Success: {success}"

    # Create Intervention
    intervention = Intervention(
        intervention_id=uuid.uuid4(),
        case_id=case.case_id,
        action_type=action_type,
        attempt_number=attempt_number,
        scheduled_at=exec_time,
        executed_at=now,
        cost=cost,
        policy_decision="ALLOW",
        policy_version="1.0.0",
        status="COMPLETED",
        idempotency_key=input_data.idempotency_key,
        created_at=now,
    )

    # Create Outcome
    amount_recovered = case.amount_at_risk if success else Decimal("0.00")
    outcome = Outcome(
        outcome_id=uuid.uuid4(),
        case_id=case.case_id,
        intervention_id=intervention.intervention_id,
        success=success,
        amount_recovered=amount_recovered,
        occurred_at=now,
        created_at=now,
    )

    return ToolResult(
        success=success,
        message=message,
        created_interventions=[intervention],
        created_outcomes=[outcome],
    )


def retry_payment(
    input_data: PaymentActionInput,
    case: RecoveryCase,
    customer: Customer,
    past_interventions: list[Intervention],
    simulator: InterventionSimulator,
) -> ToolResult:
    """Execute an immediate payment retry."""
    return _execute_payment_action(
        "RETRY_NOW", Decimal("2.00"), input_data, case, customer, past_interventions, simulator
    )


def schedule_retry(
    input_data: ScheduleRetryInput,
    case: RecoveryCase,
    customer: Customer,
    past_interventions: list[Intervention],
    simulator: InterventionSimulator,
) -> ToolResult:
    """Schedule a retry for later."""
    return _execute_payment_action(
        "RETRY_LATER",
        Decimal("2.00"),
        input_data,
        case,
        customer,
        past_interventions,
        simulator,
        scheduled_at=input_data.scheduled_at,
    )


def update_payment_method(
    input_data: BaseToolInput,
    case: RecoveryCase,
    customer: Customer,
    past_interventions: list[Intervention],
    simulator: InterventionSimulator,
) -> ToolResult:
    """Trigger a payment method update process."""
    # Re-use payment action input format but ignore payment_id internally
    action_input = PaymentActionInput(
        case_id=input_data.case_id,
        idempotency_key=input_data.idempotency_key,
        payment_id=uuid.uuid4(),
    )
    return _execute_payment_action(
        "UPDATE_PAYMENT_METHOD",
        Decimal("0.50"),
        action_input,
        case,
        customer,
        past_interventions,
        simulator,
    )


def use_alternate_gateway(
    input_data: PaymentActionInput,
    case: RecoveryCase,
    customer: Customer,
    past_interventions: list[Intervention],
    simulator: InterventionSimulator,
) -> ToolResult:
    """Attempt payment via an alternate gateway."""
    return _execute_payment_action(
        "ALTERNATE_GATEWAY",
        Decimal("3.00"),
        input_data,
        case,
        customer,
        past_interventions,
        simulator,
    )
