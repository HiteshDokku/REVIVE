"""Candidate Action Generation for the Economic Decision Engine."""

from decimal import Decimal
from typing import ClassVar

from src.database.models import Customer, RecoveryCase
from src.decision.cost import ActionCostModel
from src.decision.models import CandidateAction


class CandidateActionGenerator:
    """Deterministically generates candidate actions for a given case."""

    # Constrained action vocabulary for Milestone 7
    ALLOWED_ACTIONS: ClassVar[list[str]] = [
        "NO_ACTION",
        "RETRY_LATER",
        "EMAIL_REMINDER",
        "SMS_REMINDER",
    ]

    def __init__(self) -> None:
        """Initialize the candidate generator."""
        self.cost_model = ActionCostModel()

    def generate(self, case: RecoveryCase, customer: Customer) -> list[CandidateAction]:
        """Generate deterministic candidates.

        Args:
            case: The recovery case to evaluate.
            customer: The customer associated with the case.

        Returns:
            A list of CandidateAction objects.
        """
        candidates = []

        # Base safety checks
        is_paid = case.status == "RECOVERED"
        amount_at_risk = (
            Decimal(str(case.amount_at_risk))
            if case.amount_at_risk is not None
            else Decimal("0.00")
        )
        is_zero_value = amount_at_risk <= Decimal("0.00")

        for action_type in self.ALLOWED_ACTIONS:
            cost = self.cost_model.get_cost(action_type)

            is_eligible = True
            ineligibility_reason = None

            # Universal rules
            if is_paid and action_type != "NO_ACTION":
                is_eligible = False
                ineligibility_reason = "Case is already paid."
            elif is_zero_value and action_type != "NO_ACTION":
                is_eligible = False
                ineligibility_reason = "Amount at risk is zero or negative."

            # If the user has opted out of communication, we shouldn't send emails/SMS.
            if getattr(customer, "communication_opt_out", False) and action_type in (
                "EMAIL_REMINDER",
                "SMS_REMINDER",
            ):
                is_eligible = False
                ineligibility_reason = "Customer has opted out of communications."

            candidates.append(
                CandidateAction(
                    action_type=action_type,
                    action_cost=cost,
                    recoverable_amount=amount_at_risk,
                    is_eligible=is_eligible,
                    ineligibility_reason=ineligibility_reason,
                )
            )

        return candidates
