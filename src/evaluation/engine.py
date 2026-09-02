"""Evaluation engine for M11 financial comparison.

Core loop: Strategy selects action → Guardrails (REVIVE only) → Simulator → Realized outcome.
The simulator is the SINGLE authoritative financial ground truth.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from src.policy.guardrails import GuardrailsEngine
from src.policy.models import PolicyDecisionStatus
from src.simulator.engine import InterventionSimulator

if TYPE_CHECKING:
    from src.database.models import Customer, Payment, RecoveryCase
    from src.evaluation.strategies import BaseStrategy

# ---------------------------------------------------------------------------
# Authoritative execution costs from POLICY.md / M9 tools.
# These are the costs incurred at execution time.
# The M7 ActionCostModel uses different values for decision optimization;
# those are NOT used here.
# ---------------------------------------------------------------------------
EXECUTION_COSTS: dict[str, Decimal] = {
    "NO_ACTION": Decimal("0.00"),
    "RETRY_LATER": Decimal("2.00"),
    "RETRY_NOW": Decimal("2.00"),
    "EMAIL_REMINDER": Decimal("0.05"),
    "SMS_REMINDER": Decimal("0.30"),
    "WHATSAPP_REMINDER": Decimal("0.50"),
    "VOICE_CALL": Decimal("12.00"),
    "FINANCE_ESCALATION": Decimal("100.00"),
    "UPDATE_PAYMENT_METHOD": Decimal("0.50"),
}


class CaseEvaluationResult(BaseModel):
    """Result of evaluating a single case with a strategy."""

    case_id: uuid.UUID
    customer_id: uuid.UUID
    amount_at_risk: Decimal
    failure_reason: str
    strategy: str
    selected_action: str
    guardrail_decision: str = "N/A"
    guardrail_reason: str = ""
    guardrail_violated: list[str] = []
    executed: bool = False
    simulator_success: bool | None = None
    amount_recovered: Decimal = Decimal("0.00")
    action_cost: Decimal = Decimal("0.00")
    net_recovery: Decimal = Decimal("0.00")

    model_config = ConfigDict(arbitrary_types_allowed=True)


class EvaluationPopulationItem:
    """A single item in the evaluation population."""

    __slots__ = ("case", "customer", "trigger_payment")

    def __init__(
        self,
        case: RecoveryCase,
        customer: Customer,
        trigger_payment: Payment | None,
    ) -> None:
        self.case = case
        self.customer = customer
        self.trigger_payment = trigger_payment


def prepare_evaluation_population(
    data: dict[str, Any],
) -> list[EvaluationPopulationItem]:
    """Extract and prepare the evaluation population from synthetic data.

    Each case is presented as OPEN (point-in-time before any intervention).
    Pre-existing outcomes, interventions, and model predictions are stripped
    so that no strategy can access future information.
    """
    cust_map = {c.customer_id: c for c in data["customers"]}
    payment_map = {p.payment_id: p for p in data["payments"]}

    population: list[EvaluationPopulationItem] = []
    for case in data["recovery_cases"]:
        customer = cust_map[case.customer_id]
        trigger_payment = payment_map.get(case.source_id) if case.source_type == "payment" else None

        # Present as a fresh OPEN case — no future information
        case.status = "OPEN"
        case.recovery_probability = Decimal("0.0")
        case.recommended_action = None
        case.expected_recovery = Decimal("0.0")
        case.expected_net_recovery = Decimal("0.0")
        case.decision_confidence = Decimal("0.0")

        population.append(EvaluationPopulationItem(case, customer, trigger_payment))

    return population


class EvaluationEngine:
    """Runs strategy evaluation with realized simulator outcomes.

    Enforces strict temporal ordering:
    1. Strategy selects action (no outcome information available)
    2. Guardrails evaluate (REVIVE only)
    3. Simulator determines realized success/failure
    4. Financial metrics computed from realized outcome
    """

    def __init__(self) -> None:
        self.guardrails = GuardrailsEngine()

    def evaluate_strategy(
        self,
        strategy: BaseStrategy,
        population: list[EvaluationPopulationItem],
        eval_seed: int,
    ) -> list[CaseEvaluationResult]:
        """Evaluate a single strategy on the entire population.

        Returns a list of per-case results.
        """
        results: list[CaseEvaluationResult] = []

        for case_idx, item in enumerate(population):
            result = self._evaluate_single_case(
                strategy=strategy,
                case=item.case,
                customer=item.customer,
                trigger_payment=item.trigger_payment,
                eval_seed=eval_seed,
                case_idx=case_idx,
            )
            results.append(result)

        return results

    def _evaluate_single_case(
        self,
        strategy: BaseStrategy,
        case: RecoveryCase,
        customer: Customer,
        trigger_payment: Payment | None,
        eval_seed: int,
        case_idx: int,
    ) -> CaseEvaluationResult:
        """Evaluate a single case. Action selection BEFORE simulation."""

        # ---------------------------------------------------------------
        # 1. Strategy selects action (BEFORE any simulation)
        # ---------------------------------------------------------------
        decision = strategy.select_action(case, customer, trigger_payment)
        action = decision.selected_action

        result = CaseEvaluationResult(
            case_id=case.case_id,
            customer_id=case.customer_id,
            amount_at_risk=case.amount_at_risk,
            failure_reason=case.root_cause or "UNKNOWN",
            strategy=strategy.name,
            selected_action=action,
        )

        # ---------------------------------------------------------------
        # 2. For REVIVE, apply M8 guardrails
        # ---------------------------------------------------------------
        if strategy.uses_guardrails and decision.decision_result is not None:
            # Evaluate at a time within the recovery window
            eval_time = case.created_at + timedelta(hours=2)
            policy_result = self.guardrails.evaluate(
                decision=decision.decision_result,
                case=case,
                customer=customer,
                interventions=[],  # Fresh case — no prior interventions
                interactions=[],  # Fresh case — no prior interactions
                current_time=eval_time,
            )
            result.guardrail_decision = policy_result.decision.value
            result.guardrail_reason = policy_result.reason
            result.guardrail_violated = policy_result.violated_guardrails

            if policy_result.decision in (
                PolicyDecisionStatus.DENY,
                PolicyDecisionStatus.ESCALATE,
                PolicyDecisionStatus.NO_ACTION,
            ):
                # Action blocked — no cost, no recovery
                result.executed = False
                result.action_cost = Decimal("0.00")
                result.amount_recovered = Decimal("0.00")
                result.net_recovery = Decimal("0.00")
                return result
        else:
            result.guardrail_decision = "N/A"

        # ---------------------------------------------------------------
        # 3. If NO_ACTION, no simulation needed
        # ---------------------------------------------------------------
        if action == "NO_ACTION":
            result.executed = False
            result.action_cost = Decimal("0.00")
            result.amount_recovered = Decimal("0.00")
            result.net_recovery = Decimal("0.00")
            return result

        # ---------------------------------------------------------------
        # 4. Execute through M9 InterventionSimulator
        #    Per-case deterministic seed ensures fair comparison:
        #    same case + same action = same outcome regardless of strategy.
        # ---------------------------------------------------------------
        case_seed = (eval_seed * 100003 + case_idx * 7919) % (2**31)
        simulator = InterventionSimulator(seed=case_seed)

        success = simulator.simulate(
            action_type=action,
            failure_reason=case.root_cause or "UNKNOWN",
            reliability_score=float(customer.payment_reliability_score or 0.0),
            attempt_number=1,
        )

        # ---------------------------------------------------------------
        # 5. Calculate realized financials (Decimal-safe)
        # ---------------------------------------------------------------
        action_cost = EXECUTION_COSTS.get(action, Decimal("0.00"))
        amount_recovered = case.amount_at_risk if success else Decimal("0.00")
        net_recovery = amount_recovered - action_cost

        result.executed = True
        result.simulator_success = success
        result.amount_recovered = amount_recovered
        result.action_cost = action_cost
        result.net_recovery = net_recovery

        return result
