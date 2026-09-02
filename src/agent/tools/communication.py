"""Simulated communication execution tools."""

import random
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from src.agent.tools.base import (
    BaseToolInput,
    DuplicateExecutionError,
    ToolResult,
    check_idempotency,
)
from src.database.models import Customer, Interaction, Intervention, RecoveryCase
from src.faults.injector import get_fault_injector
from src.faults.models import FaultType


class SendMessageInput(BaseToolInput):
    customer_id: uuid.UUID
    channel: str
    message: str


def _execute_communication_action(
    action_type: str,
    cost: Decimal,
    input_data: SendMessageInput,
    case: RecoveryCase,
    customer: Customer,
    past_interventions: list[Intervention],
) -> ToolResult:
    """Shared logic for executing simulated communication actions."""
    try:
        check_idempotency(input_data.idempotency_key, past_interventions, [])
    except DuplicateExecutionError as e:
        return ToolResult(success=False, message=str(e))

    now = datetime.now(UTC)

    # Check for API_TIMEOUT
    injector = get_fault_injector()
    if injector.should_inject(FaultType.API_TIMEOUT, str(case.case_id)):
        return ToolResult(success=False, message="API timeout: execution state unknown/retryable.")

    # Calculate attempt number
    attempt_number = sum(1 for i in past_interventions if i.action_type == action_type) + 1

    # Create Intervention
    intervention = Intervention(
        intervention_id=uuid.uuid4(),
        case_id=case.case_id,
        action_type=action_type,
        attempt_number=attempt_number,
        scheduled_at=now,
        executed_at=now,
        cost=cost,
        policy_decision="ALLOW",
        policy_version="1.0.0",
        status="COMPLETED",
        idempotency_key=input_data.idempotency_key,
        created_at=now,
    )

    # Simulate a customer interaction (response)
    hinglish_examples = [
        "Kal shaam payment kar dunga.",
        "Aaj funds nahi hai, weekend pe karunga.",
        "Payment already kar diya hai.",
        "Please mujhe message mat karna.",
    ]

    created_interactions = []

    # 20% chance of customer response for communications
    if random.random() < 0.2:
        cust_resp = random.choice(hinglish_examples)
        is_promise = "kar dunga" in cust_resp or "karunga" in cust_resp

        interaction = Interaction(
            interaction_id=uuid.uuid4(),
            customer_id=customer.customer_id,
            recovery_case_id=case.case_id,
            channel=input_data.channel,
            occurred_at=now + timedelta(minutes=random.randint(5, 60)),
            message=input_data.message,
            customer_response=cust_resp,
            intent="PROMISE_TO_PAY" if is_promise else None,
            promise_to_pay=is_promise,
            created_at=now,
        )
        created_interactions.append(interaction)

    return ToolResult(
        success=True,
        message=f"Message sent via {input_data.channel}.",
        created_interventions=[intervention],
        created_interactions=created_interactions,
    )


def send_message(
    input_data: SendMessageInput,
    case: RecoveryCase,
    customer: Customer,
    past_interventions: list[Intervention],
) -> ToolResult:
    """Send an SMS, EMAIL, or WHATSAPP message."""
    cost_map = {"SMS": Decimal("0.30"), "EMAIL": Decimal("0.05"), "WHATSAPP": Decimal("0.50")}

    channel = input_data.channel.upper()
    if channel not in cost_map:
        return ToolResult(success=False, message=f"Unsupported channel: {channel}")

    action_type = f"{channel}_REMINDER"
    cost = cost_map[channel]

    return _execute_communication_action(
        action_type, cost, input_data, case, customer, past_interventions
    )


def initiate_voice_call(
    input_data: SendMessageInput,
    case: RecoveryCase,
    customer: Customer,
    past_interventions: list[Intervention],
) -> ToolResult:
    """Initiate an automated or agent-assisted voice call."""
    input_data.channel = "VOICE"
    return _execute_communication_action(
        "VOICE_CALL", Decimal("12.00"), input_data, case, customer, past_interventions
    )
