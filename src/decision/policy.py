"""Decision Policy implementations for the Economic Decision Engine."""

from abc import ABC, abstractmethod
from decimal import Decimal

from src.database.models import Customer, Payment, RecoveryCase
from src.decision.candidates import CandidateActionGenerator
from src.decision.models import DecisionResult, EvaluatedAction
from src.models.recovery_propensity import RecoveryPropensityModel


class DecisionPolicy(ABC):
    """Abstract base class for all decision policies."""

    @abstractmethod
    def evaluate(
        self,
        case: RecoveryCase,
        customer: Customer,
        attempt_number: int = 1,
        trigger_payment: Payment | None = None,
    ) -> DecisionResult:
        """Evaluate a case and select the best action.

        Args:
            case: The recovery case.
            customer: The customer involved.
            attempt_number: The current attempt sequence number.
            trigger_payment: The payment that triggered this case.

        Returns:
            A DecisionResult containing the selected action and rationale.
        """
        pass


class ExpectedValuePolicy(DecisionPolicy):
    """Selects the action that maximizes expected net monetary recovery."""

    def __init__(self, propensity_model: RecoveryPropensityModel | None = None) -> None:
        """Initialize the policy.

        Args:
            propensity_model: The underlying model. If None, instantiates a default.
        """
        self.generator = CandidateActionGenerator()
        self.model = propensity_model or RecoveryPropensityModel()

    def evaluate(
        self,
        case: RecoveryCase,
        customer: Customer,
        attempt_number: int = 1,
        trigger_payment: Payment | None = None,
    ) -> DecisionResult:
        """Evaluate and rank actions by Expected Net Recovery."""
        candidates = self.generator.generate(case, customer)
        evaluated_actions = []

        for candidate in candidates:
            # Skip ineligible actions
            if not candidate.is_eligible:
                evaluated_actions.append(
                    EvaluatedAction(
                        **candidate.model_dump(),
                        recovery_probability=0.0,
                        confidence=1.0,
                        expected_recovery=Decimal("0.00"),
                        expected_net_recovery=Decimal("0.00"),
                    )
                )
                continue

            # Handle NO_ACTION deterministically
            if candidate.action_type == "NO_ACTION":
                evaluated_actions.append(
                    EvaluatedAction(
                        **candidate.model_dump(),
                        recovery_probability=0.0,
                        confidence=1.0,
                        expected_recovery=Decimal("0.00"),
                        expected_net_recovery=-candidate.action_cost,
                    )
                )
                continue

            try:
                # Query the model for probability
                pred = self.model.predict(
                    case=case,
                    customer=customer,
                    action_type=candidate.action_type,
                    attempt_number=attempt_number,
                    trigger_payment=trigger_payment,
                )

                prob = float(pred.get("recovery_probability", 0.0))
                conf = float(pred.get("confidence", 1.0))
                model_ver = pred.get("model_version", "unknown")

                # Math MUST use Decimal
                expected_recovery = Decimal(str(prob)) * candidate.recoverable_amount
                expected_net_recovery = expected_recovery - candidate.action_cost

                evaluated_actions.append(
                    EvaluatedAction(
                        **candidate.model_dump(),
                        recovery_probability=prob,
                        confidence=conf,
                        expected_recovery=expected_recovery,
                        expected_net_recovery=expected_net_recovery,
                        model_version=model_ver,
                    )
                )

            except Exception as e:
                # Fallback on failure (e.g., missing model)
                evaluated_actions.append(
                    EvaluatedAction(
                        **candidate.model_dump(exclude={"is_eligible", "ineligibility_reason"}),
                        is_eligible=False,
                        ineligibility_reason=f"Model evaluation failed: {e}",
                        recovery_probability=0.0,
                        confidence=1.0,
                        expected_recovery=Decimal("0.00"),
                        expected_net_recovery=Decimal("0.00"),
                    )
                )

        # Ranking logic:
        # 1. Expected net recovery (highest)
        # 2. Probability (highest)
        # 3. Cost (lowest)
        # 4. Action type (alphabetical)

        def rank_key(a: EvaluatedAction) -> tuple[bool, float, float, float, str]:
            # Return tuple to sort descending by net_rec, prob; ascending by cost, name
            return (
                not a.is_eligible,  # Ineligible actions last
                -float(a.expected_net_recovery),  # Negative because we want descending
                -a.recovery_probability,  # Descending
                float(a.action_cost),  # Ascending (lower cost is better)
                a.action_type,  # Ascending (alphabetical)
            )

        ranked = sorted(evaluated_actions, key=rank_key)

        # Determine the selected action
        best_action = ranked[0]

        # Explicit NO_ACTION fallback condition:
        # If the best eligible action has negative EV (and it's not NO_ACTION itself),
        # or if there are no eligible actions at all, default to NO_ACTION.
        # Note: Since NO_ACTION is in the candidates, it has 0.0 EV. If all other
        # actions have negative EV, NO_ACTION (with 0.0 EV) will naturally outrank them.
        # But just to be strictly compliant, we enforce it.

        if not best_action.is_eligible or best_action.expected_net_recovery < Decimal("0.00"):
            # Find NO_ACTION in ranked list
            no_action = next((a for a in ranked if a.action_type == "NO_ACTION"), None)
            if no_action:
                best_action = no_action

        explanation = (
            f"Action {best_action.action_type} selected. "
            f"Amount at risk: {best_action.recoverable_amount}, "
            f"Cost: {best_action.action_cost}. "
            f"Model P(recovery) = {best_action.recovery_probability:.4f}. "
            f"Expected Net Recovery = {best_action.expected_net_recovery:.4f}. "
        )
        if best_action.action_type == "NO_ACTION":
            explanation += "Fallback to NO_ACTION because all alternatives had negative expected value or were ineligible."
        else:
            explanation += "This action maximized Expected Net Recovery among eligible candidates."

        return DecisionResult(
            case_id=str(case.case_id),
            selected_action=best_action.action_type,
            expected_net_recovery=best_action.expected_net_recovery,
            expected_recovery=best_action.expected_recovery,
            recovery_probability=best_action.recovery_probability,
            confidence=best_action.confidence,
            action_cost=best_action.action_cost,
            model_version=best_action.model_version,
            ranked_actions=ranked,
            explanation=explanation,
        )
