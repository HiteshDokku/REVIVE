"""Data models and schemas for Policy and Guardrails."""

import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class PolicyDecisionStatus(StrEnum):
    """The final deterministic outcome of the policy evaluation."""

    ALLOW = "ALLOW"
    DENY = "DENY"
    ESCALATE = "ESCALATE"
    NO_ACTION = "NO_ACTION"


class PolicyEvaluationResult(BaseModel):
    """The comprehensive result of a guardrail evaluation."""

    case_id: uuid.UUID
    decision: PolicyDecisionStatus
    action_type: str
    reason: str
    guardrails_evaluated: list[str] = Field(default_factory=list)
    violated_guardrails: list[str] = Field(default_factory=list)
    policy_version: str = "1.0.0"

    # Optional metadata for transparency
    metadata: dict[str, Any] = Field(default_factory=dict)
