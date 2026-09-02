"""Action Cost Model configuration for the Economic Decision Engine."""

from decimal import Decimal

# Centralized deterministic cost assumptions for interventions.
# Using Decimal-safe values for all monetary operations.
ACTION_COSTS: dict[str, Decimal] = {
    "NO_ACTION": Decimal("0.00"),
    "EMAIL_REMINDER": Decimal("0.05"),
    "SMS_REMINDER": Decimal("0.15"),
    "RETRY_LATER": Decimal("2.00"),
}


class ActionCostModel:
    """Provides deterministic cost lookups for candidate actions."""

    @classmethod
    def get_cost(cls, action_type: str) -> Decimal:
        """Get the monetary cost of an action.

        Args:
            action_type: The type of intervention.

        Returns:
            The cost as a Decimal. Raises ValueError if unknown.
        """
        if action_type not in ACTION_COSTS:
            raise ValueError(f"Unknown action type: {action_type}")
        return ACTION_COSTS[action_type]
