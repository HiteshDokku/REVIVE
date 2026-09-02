"""Base contract for all simulated M9 Agent Tools."""

import uuid

from pydantic import BaseModel, ConfigDict

from src.database.models import Interaction, Intervention, Outcome
from src.faults.injector import get_fault_injector
from src.faults.models import FaultType


class BaseToolInput(BaseModel):
    """Base input schema for all tools requiring idempotency."""

    case_id: uuid.UUID
    idempotency_key: str

    model_config = ConfigDict(frozen=True)


class ToolResult(BaseModel):
    """Standardized output from a tool execution."""

    success: bool
    message: str
    created_interventions: list[Intervention] = []
    created_outcomes: list[Outcome] = []
    created_interactions: list[Interaction] = []

    model_config = ConfigDict(arbitrary_types_allowed=True)


class DuplicateExecutionError(Exception):
    """Raised when an idempotency key is reused."""

    pass


def check_idempotency(
    idempotency_key: str,
    past_interventions: list[Intervention],
    past_interactions: list[Interaction],
) -> None:
    """Check if the idempotency key has already been executed."""
    injector = get_fault_injector()
    # If a duplicate fault is requested globally or for any specific case
    # Here we don't have case_id in the arguments, so we check generally without case_id.
    # In M13 testing, we can just inject DUPLICATE_EVENT.
    if injector.should_inject(FaultType.DUPLICATE_EVENT):
        raise DuplicateExecutionError(
            f"Idempotency key {idempotency_key} already used (simulated)."
        )

    for inv in past_interventions:
        if inv.idempotency_key == idempotency_key:
            raise DuplicateExecutionError(f"Idempotency key {idempotency_key} already used.")

    # Optional: could check interactions if they use idempotency keys
