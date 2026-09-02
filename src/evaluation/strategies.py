"""Evaluation strategies for M11 financial comparison.

Each strategy selects an action for a given case.
Action selection MUST occur BEFORE simulated execution.
Strategies MUST NOT access outcome, amount_recovered, or status_after.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.database.models import Customer, Payment, RecoveryCase
from src.decision.models import DecisionResult
from src.decision.policy import ExpectedValuePolicy


@dataclass
class StrategyDecision:
    """Result of a strategy's action selection."""

    selected_action: str
    decision_result: DecisionResult | None = None


class BaseStrategy(ABC):
    """Abstract base class for evaluation strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this strategy."""
        ...

    @property
    def uses_guardrails(self) -> bool:
        """Whether this strategy passes through M8 guardrails."""
        return False

    @abstractmethod
    def select_action(
        self,
        case: RecoveryCase,
        customer: Customer,
        trigger_payment: Payment | None = None,
    ) -> StrategyDecision:
        """Select an action for the given case.

        This method MUST NOT access any outcome or post-decision information.
        """
        ...


class NoActionStrategy(BaseStrategy):
    """Always selects NO_ACTION. Zero cost, zero recovery."""

    @property
    def name(self) -> str:
        return "NO_ACTION"

    def select_action(
        self,
        case: RecoveryCase,
        customer: Customer,
        trigger_payment: Payment | None = None,
    ) -> StrategyDecision:
        return StrategyDecision(selected_action="NO_ACTION")


class AlwaysRetryStrategy(BaseStrategy):
    """Always selects RETRY_LATER."""

    @property
    def name(self) -> str:
        return "ALWAYS_RETRY"

    def select_action(
        self,
        case: RecoveryCase,
        customer: Customer,
        trigger_payment: Payment | None = None,
    ) -> StrategyDecision:
        return StrategyDecision(selected_action="RETRY_LATER")


class GenericReminderStrategy(BaseStrategy):
    """Always selects EMAIL_REMINDER."""

    @property
    def name(self) -> str:
        return "GENERIC_REMINDER"

    def select_action(
        self,
        case: RecoveryCase,
        customer: Customer,
        trigger_payment: Payment | None = None,
    ) -> StrategyDecision:
        return StrategyDecision(selected_action="EMAIL_REMINDER")


class ReviveStrategy(BaseStrategy):
    """Uses the full REVIVE pipeline: M6 propensity → M7 decision → M8 guardrails.

    The decision engine (ExpectedValuePolicy) internally calls:
    - CandidateActionGenerator (M7)
    - RecoveryPropensityModel (M6)
    - Expected-value ranking (M7)

    Guardrails are applied by the EvaluationEngine.
    """

    @property
    def name(self) -> str:
        return "REVIVE"

    @property
    def uses_guardrails(self) -> bool:
        return True

    def __init__(self) -> None:
        self._policy = ExpectedValuePolicy()

    def select_action(
        self,
        case: RecoveryCase,
        customer: Customer,
        trigger_payment: Payment | None = None,
    ) -> StrategyDecision:
        result = self._policy.evaluate(
            case=case,
            customer=customer,
            attempt_number=1,
            trigger_payment=trigger_payment,
        )
        return StrategyDecision(
            selected_action=result.selected_action,
            decision_result=result,
        )
