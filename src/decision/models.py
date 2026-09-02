"""Data models for the Economic Decision Engine."""

from decimal import Decimal

from pydantic import BaseModel, Field


class CandidateAction(BaseModel):
    """Represents a potential recovery action."""

    action_type: str = Field(..., description="The type of action (e.g., RETRY_LATER)")
    action_cost: Decimal = Field(
        ..., description="The deterministic cost of performing this action"
    )
    recoverable_amount: Decimal = Field(
        ..., description="The amount at risk that could be recovered"
    )
    is_eligible: bool = Field(
        True, description="Whether this action is currently eligible to be performed"
    )
    ineligibility_reason: str | None = Field(None, description="Reason for ineligibility, if any")


class EvaluatedAction(CandidateAction):
    """A candidate action that has been evaluated by the propensity model."""

    recovery_probability: float = Field(
        0.0, description="Predicted probability of recovery if this action is taken"
    )
    confidence: float = Field(1.0, description="Model confidence in the probability estimate")
    expected_recovery: Decimal = Field(
        Decimal("0.0"), description="recovery_probability * recoverable_amount"
    )
    expected_net_recovery: Decimal = Field(
        Decimal("0.0"), description="expected_recovery - action_cost"
    )
    model_version: str | None = Field(
        None, description="Version of the model used for this evaluation"
    )


class DecisionResult(BaseModel):
    """The final decision produced by the policy engine."""

    case_id: str = Field(..., description="The ID of the recovery case evaluated")
    selected_action: str = Field(..., description="The action type selected by the policy")
    expected_net_recovery: Decimal = Field(
        ..., description="The expected net recovery of the selected action"
    )
    expected_recovery: Decimal = Field(
        ..., description="The expected recovery amount of the selected action"
    )
    recovery_probability: float = Field(
        ..., description="The probability of the selected action succeeding"
    )
    confidence: float = Field(
        ..., description="The confidence in the selected action's probability"
    )
    action_cost: Decimal = Field(..., description="The cost of the selected action")
    model_version: str | None = Field(None, description="Version of the model used")
    ranked_actions: list[EvaluatedAction] = Field(
        default_factory=list, description="All evaluated actions, ordered by rank"
    )
    explanation: str = Field(..., description="Natural language reasoning for the decision")
