"""Audit and outcome recording tools."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from src.agent.tools.base import (
    BaseToolInput,
    DuplicateExecutionError,
    ToolResult,
    check_idempotency,
)
from src.database.models import Intervention, Outcome


class FinanceEscalationInput(BaseToolInput):
    reason: str


class RecordOutcomeInput(BaseToolInput):
    status: str
    amount_recovered: Decimal


def create_finance_escalation(
    input_data: FinanceEscalationInput, past_interventions: list[Intervention]
) -> ToolResult:
    """Create a manual finance escalation task."""
    try:
        check_idempotency(input_data.idempotency_key, past_interventions, [])
    except DuplicateExecutionError as e:
        return ToolResult(success=False, message=str(e))

    now = datetime.now(UTC)

    intervention = Intervention(
        intervention_id=uuid.uuid4(),
        case_id=input_data.case_id,
        action_type="FINANCE_ESCALATION",
        attempt_number=1,
        scheduled_at=now,
        executed_at=now,
        cost=Decimal("100.00"),  # From POLICY.md
        policy_decision="ALLOW",
        policy_version="1.0.0",
        status="COMPLETED",
        idempotency_key=input_data.idempotency_key,
        created_at=now,
    )

    return ToolResult(
        success=True,
        message=f"Finance escalation created. Reason: {input_data.reason}",
        created_interventions=[intervention],
    )


def record_outcome(input_data: RecordOutcomeInput, intervention_id: uuid.UUID) -> ToolResult:
    """Explicitly record a final outcome for a case (used directly by agent or webhooks)."""
    # Note: Idempotency here would check the Outcome table.
    now = datetime.now(UTC)
    success = input_data.status == "RECOVERED"

    outcome = Outcome(
        outcome_id=uuid.uuid4(),
        case_id=input_data.case_id,
        intervention_id=intervention_id,
        success=success,
        amount_recovered=input_data.amount_recovered,
        occurred_at=now,
        created_at=now,
    )

    return ToolResult(
        success=True, message=f"Outcome recorded: {input_data.status}", created_outcomes=[outcome]
    )
