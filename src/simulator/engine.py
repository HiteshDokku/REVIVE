"""Independent simulation engine for action outcomes (Milestone 9)."""

import random


class InterventionSimulator:
    """
    Simulates the causal effectiveness of actions on a recovery case.
    Uses the exact probabilistic relationships defined in the synthetic environment.
    """

    def __init__(self, seed: int = 42) -> None:
        self.rng = random.Random(seed)

    def simulate(
        self,
        action_type: str,
        failure_reason: str,
        reliability_score: float,
        attempt_number: int,
    ) -> bool:
        """
        Evaluate whether the given action succeeds based on causal logic.
        """
        base_prob = 0.01

        if failure_reason in ("NETWORK_TIMEOUT", "GATEWAY_FAILURE", "TEMPORARY_ISSUER_DECLINE"):
            if action_type == "RETRY_LATER" or action_type == "RETRY_NOW":
                base_prob = 0.70 + (0.20 * reliability_score)
            else:
                base_prob = 0.05
        elif failure_reason in ("EXPIRED_CARD", "INVALID_PAYMENT_METHOD"):
            if action_type == "RETRY_LATER" or action_type == "RETRY_NOW":
                base_prob = 0.0  # Cannot retry an expired card
            elif action_type == "UPDATE_PAYMENT_METHOD":
                base_prob = 0.80 + (0.10 * reliability_score)
            else:
                base_prob = 0.15 + (0.35 * reliability_score)
        elif failure_reason == "INSUFFICIENT_FUNDS":
            if action_type == "RETRY_LATER" or action_type == "RETRY_NOW":
                base_prob = 0.10 + (0.20 * reliability_score)
            else:
                base_prob = 0.20 + (0.30 * reliability_score)
        elif failure_reason == "CUSTOMER_ABANDONMENT":
            if action_type == "RETRY_LATER" or action_type == "RETRY_NOW":
                base_prob = 0.0
            else:
                base_prob = 0.10 + (0.20 * reliability_score)
        elif failure_reason == "OVERDUE_INVOICE":
            base_prob = 0.40 if "REMINDER" in action_type else 0.0

        # Diminishing returns on successive attempts
        base_prob *= 0.8 ** (max(1, attempt_number) - 1)

        return self.rng.random() < base_prob
