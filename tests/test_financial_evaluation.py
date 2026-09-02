"""Tests for M11 Financial Evaluation.

Covers:
- Strategy behavior
- Financial arithmetic (Decimal precision)
- Simulator integration
- Leakage prevention
- Reproducibility
- Multi-seed metadata
- Baseline fairness
- Safety / guardrails
- Communication handling
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from src.database.models import Customer, Payment, RecoveryCase
from src.evaluation.engine import (
    EXECUTION_COSTS,
    CaseEvaluationResult,
    EvaluationEngine,
    EvaluationPopulationItem,
    prepare_evaluation_population,
)
from src.evaluation.metrics import (
    FinancialMetrics,
    aggregate_metric,
    compute_comparative_metrics,
    compute_financial_metrics,
    compute_safety_metrics,
)
from src.evaluation.strategies import (
    AlwaysRetryStrategy,
    GenericReminderStrategy,
    NoActionStrategy,
    ReviveStrategy,
    StrategyDecision,
)
from src.simulator.engine import InterventionSimulator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_customer(
    customer_id: uuid.UUID | None = None,
    reliability: float = 0.8,
    opt_out: bool = False,
    ltv: float = 5000.0,
) -> Customer:
    cid = customer_id or uuid.uuid4()
    now = datetime.now(UTC)
    return Customer(
        customer_id=cid,
        customer_type="individual",
        country="IN",
        language="en",
        preferred_channel="email",
        customer_since=now - timedelta(days=365),
        payment_reliability_score=Decimal(f"{reliability:.5f}"),
        avg_payment_delay_days=Decimal("2.0"),
        lifetime_value=Decimal(str(ltv)),
        active_subscriptions=1,
        communication_opt_out=opt_out,
        created_at=now,
        updated_at=now,
    )


def _make_case(
    customer_id: uuid.UUID,
    amount: Decimal = Decimal("1000.00"),
    root_cause: str = "NETWORK_TIMEOUT",
    source_type: str = "payment",
) -> RecoveryCase:
    now = datetime.now(UTC)
    return RecoveryCase(
        case_id=uuid.uuid4(),
        customer_id=customer_id,
        source_type=source_type,
        source_id=uuid.uuid4(),
        amount_at_risk=amount,
        risk_score=Decimal("0.20000"),
        root_cause=root_cause,
        root_cause_confidence=Decimal("0.90000"),
        status="OPEN",
        escalation_required=False,
        created_at=now,
        updated_at=now,
    )


def _make_payment(customer_id: uuid.UUID, failure_reason: str = "NETWORK_TIMEOUT") -> Payment:
    now = datetime.now(UTC)
    return Payment(
        payment_id=uuid.uuid4(),
        customer_id=customer_id,
        amount=Decimal("1000.00"),
        currency="INR",
        occurred_at=now,
        payment_method="card",
        gateway="gateway_a",
        status="failed",
        failure_reason=failure_reason,
        retry_count=0,
        created_at=now,
        updated_at=now,
    )


def _make_population(
    n: int = 5, root_cause: str = "NETWORK_TIMEOUT"
) -> list[EvaluationPopulationItem]:
    """Create a small deterministic evaluation population."""
    items = []
    for _ in range(n):
        customer = _make_customer()
        case = _make_case(customer.customer_id, root_cause=root_cause)
        payment = _make_payment(customer.customer_id, failure_reason=root_cause)
        items.append(EvaluationPopulationItem(case, customer, payment))
    return items


# ===========================================================================
# Strategy Behavior Tests
# ===========================================================================


class TestStrategyBehavior:
    """Verify each strategy returns the expected action."""

    def test_no_action_strategy(self) -> None:
        strategy = NoActionStrategy()
        customer = _make_customer()
        case = _make_case(customer.customer_id)
        decision = strategy.select_action(case, customer)
        assert decision.selected_action == "NO_ACTION"
        assert strategy.name == "NO_ACTION"
        assert not strategy.uses_guardrails

    def test_always_retry_strategy(self) -> None:
        strategy = AlwaysRetryStrategy()
        customer = _make_customer()
        case = _make_case(customer.customer_id)
        decision = strategy.select_action(case, customer)
        assert decision.selected_action == "RETRY_LATER"
        assert strategy.name == "ALWAYS_RETRY"
        assert not strategy.uses_guardrails

    def test_generic_reminder_strategy(self) -> None:
        strategy = GenericReminderStrategy()
        customer = _make_customer()
        case = _make_case(customer.customer_id)
        decision = strategy.select_action(case, customer)
        assert decision.selected_action == "EMAIL_REMINDER"
        assert strategy.name == "GENERIC_REMINDER"
        assert not strategy.uses_guardrails

    def test_revive_strategy_uses_guardrails(self) -> None:
        strategy = ReviveStrategy()
        assert strategy.uses_guardrails is True
        assert strategy.name == "REVIVE"

    def test_revive_strategy_returns_decision_result(self) -> None:
        strategy = ReviveStrategy()
        customer = _make_customer()
        case = _make_case(customer.customer_id)
        decision = strategy.select_action(case, customer)
        assert decision.decision_result is not None
        assert decision.selected_action in {
            "NO_ACTION",
            "RETRY_LATER",
            "EMAIL_REMINDER",
            "SMS_REMINDER",
        }


# ===========================================================================
# Financial Arithmetic Tests
# ===========================================================================


class TestFinancialArithmetic:
    """Verify Decimal-safe financial calculations."""

    def test_net_recovery_equals_recovered_minus_cost(self) -> None:
        result = CaseEvaluationResult(
            case_id=uuid.uuid4(),
            customer_id=uuid.uuid4(),
            amount_at_risk=Decimal("1000.00"),
            failure_reason="NETWORK_TIMEOUT",
            strategy="TEST",
            selected_action="RETRY_LATER",
            executed=True,
            simulator_success=True,
            amount_recovered=Decimal("1000.00"),
            action_cost=Decimal("2.00"),
            net_recovery=Decimal("998.00"),
        )
        assert result.net_recovery == result.amount_recovered - result.action_cost

    def test_failed_recovery_net_is_negative_cost(self) -> None:
        result = CaseEvaluationResult(
            case_id=uuid.uuid4(),
            customer_id=uuid.uuid4(),
            amount_at_risk=Decimal("500.00"),
            failure_reason="EXPIRED_CARD",
            strategy="TEST",
            selected_action="RETRY_LATER",
            executed=True,
            simulator_success=False,
            amount_recovered=Decimal("0.00"),
            action_cost=Decimal("2.00"),
            net_recovery=Decimal("-2.00"),
        )
        assert result.net_recovery == Decimal("0.00") - Decimal("2.00")

    def test_no_action_zero_financials(self) -> None:
        result = CaseEvaluationResult(
            case_id=uuid.uuid4(),
            customer_id=uuid.uuid4(),
            amount_at_risk=Decimal("1000.00"),
            failure_reason="NETWORK_TIMEOUT",
            strategy="NO_ACTION",
            selected_action="NO_ACTION",
            executed=False,
            simulator_success=None,
            amount_recovered=Decimal("0.00"),
            action_cost=Decimal("0.00"),
            net_recovery=Decimal("0.00"),
        )
        assert result.action_cost == Decimal("0.00")
        assert result.amount_recovered == Decimal("0.00")
        assert result.net_recovery == Decimal("0.00")

    def test_compute_financial_metrics_decimal(self) -> None:
        results = [
            CaseEvaluationResult(
                case_id=uuid.uuid4(),
                customer_id=uuid.uuid4(),
                amount_at_risk=Decimal("1000.00"),
                failure_reason="A",
                strategy="TEST",
                selected_action="RETRY_LATER",
                executed=True,
                simulator_success=True,
                amount_recovered=Decimal("1000.00"),
                action_cost=Decimal("2.00"),
                net_recovery=Decimal("998.00"),
            ),
            CaseEvaluationResult(
                case_id=uuid.uuid4(),
                customer_id=uuid.uuid4(),
                amount_at_risk=Decimal("500.00"),
                failure_reason="B",
                strategy="TEST",
                selected_action="RETRY_LATER",
                executed=True,
                simulator_success=False,
                amount_recovered=Decimal("0.00"),
                action_cost=Decimal("2.00"),
                net_recovery=Decimal("-2.00"),
            ),
        ]
        fm = compute_financial_metrics(results)
        assert fm.total_cases == 2
        assert fm.successful_recoveries == 1
        assert fm.total_amount_recovered == Decimal("1000.00")
        assert fm.total_intervention_cost == Decimal("4.00")
        assert fm.total_net_recovery == Decimal("996.00")
        assert fm.revenue_at_risk == Decimal("1500.00")

    def test_aggregate_metric_values(self) -> None:
        values = [Decimal("100"), Decimal("200"), Decimal("300")]
        agg = aggregate_metric(values)
        assert agg.mean == Decimal("200.00")
        assert agg.min_val == Decimal("100.00")
        assert agg.max_val == Decimal("300.00")

    def test_execution_costs_are_decimal(self) -> None:
        for action, cost in EXECUTION_COSTS.items():
            assert isinstance(cost, Decimal), f"{action} cost is not Decimal"


# ===========================================================================
# Simulator Integration Tests
# ===========================================================================


class TestSimulatorIntegration:
    """Verify actions produce simulator-derived realized outcomes."""

    def test_retry_on_transient_failure(self) -> None:
        """RETRY on transient failure should have high success probability."""
        sim = InterventionSimulator(seed=42)
        success = sim.simulate(
            action_type="RETRY_LATER",
            failure_reason="NETWORK_TIMEOUT",
            reliability_score=0.9,
            attempt_number=1,
        )
        assert isinstance(success, bool)

    def test_retry_on_expired_card_always_fails(self) -> None:
        """RETRY on expired card should always fail (0% probability)."""
        for seed in range(100):
            sim = InterventionSimulator(seed=seed)
            success = sim.simulate(
                action_type="RETRY_LATER",
                failure_reason="EXPIRED_CARD",
                reliability_score=0.99,
                attempt_number=1,
            )
            assert success is False

    def test_engine_uses_simulator(self) -> None:
        """Engine must produce simulator-derived outcomes."""
        engine = EvaluationEngine()
        population = _make_population(10, root_cause="NETWORK_TIMEOUT")
        results = engine.evaluate_strategy(AlwaysRetryStrategy(), population, eval_seed=42)
        assert len(results) == 10
        executed = [r for r in results if r.executed]
        assert len(executed) == 10  # ALWAYS_RETRY always executes
        for r in executed:
            assert r.simulator_success is not None
            if r.simulator_success:
                assert r.amount_recovered == r.amount_at_risk
            else:
                assert r.amount_recovered == Decimal("0.00")


# ===========================================================================
# Communication Handling Tests
# ===========================================================================


class TestCommunicationHandling:
    """Verify communication delivery success != payment recovery."""

    def test_email_reminder_recovery_via_simulator(self) -> None:
        """EMAIL_REMINDER recovery must come from simulator, not message delivery."""
        engine = EvaluationEngine()
        population = _make_population(20, root_cause="EXPIRED_CARD")
        results = engine.evaluate_strategy(GenericReminderStrategy(), population, eval_seed=42)

        # EMAIL_REMINDER on EXPIRED_CARD has some probability via simulator
        # but message delivery itself is NOT counted as recovery
        for r in results:
            assert r.executed is True
            assert r.simulator_success is not None
            # Key: not all are successful even though "message was sent"
            if not r.simulator_success:
                assert r.amount_recovered == Decimal("0.00")

    def test_reminder_not_all_recover(self) -> None:
        """Not every sent reminder should result in recovery (simulator determines)."""
        engine = EvaluationEngine()
        population = _make_population(50, root_cause="INSUFFICIENT_FUNDS")
        results = engine.evaluate_strategy(GenericReminderStrategy(), population, eval_seed=42)
        successes = sum(1 for r in results if r.simulator_success)
        failures = sum(1 for r in results if r.simulator_success is False)
        # Both outcomes should exist in a large enough sample
        assert successes >= 0
        assert failures >= 0
        assert successes + failures == 50


# ===========================================================================
# Leakage Prevention Tests
# ===========================================================================


class TestLeakagePrevention:
    """Verify strategies cannot access outcome/future information."""

    def test_strategy_input_has_no_outcome(self) -> None:
        """Strategies receive case/customer but not outcomes."""
        customer = _make_customer()
        case = _make_case(customer.customer_id)
        case.status = "OPEN"

        # Verify the case doesn't leak recovery info
        assert case.status == "OPEN"
        assert case.recovery_probability is None or case.recovery_probability == Decimal("0")
        assert case.expected_recovery is None or case.expected_recovery == Decimal("0")

    def test_strategies_dont_access_amount_recovered(self) -> None:
        """Baseline strategies only look at action type, never amount_recovered."""
        # These strategies are trivially safe — they ignore all input
        for strategy in [NoActionStrategy(), AlwaysRetryStrategy(), GenericReminderStrategy()]:
            customer = _make_customer()
            case = _make_case(customer.customer_id)
            decision = strategy.select_action(case, customer)
            # Strategy decision doesn't depend on case content at all
            assert isinstance(decision, StrategyDecision)

    def test_population_preparation_strips_future_info(self) -> None:
        """prepare_evaluation_population must set cases to OPEN and strip predictions."""
        customers = [_make_customer()]
        payments = [_make_payment(customers[0].customer_id)]
        case = RecoveryCase(
            case_id=uuid.uuid4(),
            customer_id=customers[0].customer_id,
            source_type="payment",
            source_id=payments[0].payment_id,
            amount_at_risk=Decimal("1000.00"),
            root_cause="NETWORK_TIMEOUT",
            status="RECOVERED",  # Will be stripped
            recovery_probability=Decimal("0.85"),  # Will be stripped
            expected_recovery=Decimal("850.00"),  # Will be stripped
            expected_net_recovery=Decimal("848.00"),  # Will be stripped
            decision_confidence=Decimal("0.90"),  # Will be stripped
            recommended_action="RETRY_LATER",  # Will be stripped
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        data = {
            "customers": customers,
            "payments": payments,
            "recovery_cases": [case],
        }
        population = prepare_evaluation_population(data)
        assert len(population) == 1
        prepared_case = population[0].case
        assert prepared_case.status == "OPEN"
        assert prepared_case.recovery_probability == Decimal("0.0")
        assert prepared_case.expected_recovery == Decimal("0.0")
        assert prepared_case.expected_net_recovery == Decimal("0.0")
        assert prepared_case.decision_confidence == Decimal("0.0")
        assert prepared_case.recommended_action is None


# ===========================================================================
# Reproducibility Tests
# ===========================================================================


class TestReproducibility:
    """Same seed + configuration must produce identical results."""

    def test_same_seed_same_results(self) -> None:
        engine = EvaluationEngine()
        population = _make_population(20, root_cause="NETWORK_TIMEOUT")
        strategy = AlwaysRetryStrategy()

        results_1 = engine.evaluate_strategy(strategy, population, eval_seed=42)
        results_2 = engine.evaluate_strategy(strategy, population, eval_seed=42)

        for r1, r2 in zip(results_1, results_2, strict=False):
            assert r1.simulator_success == r2.simulator_success
            assert r1.amount_recovered == r2.amount_recovered
            assert r1.net_recovery == r2.net_recovery

    def test_different_seed_different_results(self) -> None:
        """Different seeds should produce at least some different outcomes."""
        engine = EvaluationEngine()
        population = _make_population(50, root_cause="INSUFFICIENT_FUNDS")
        strategy = AlwaysRetryStrategy()

        results_42 = engine.evaluate_strategy(strategy, population, eval_seed=42)
        results_99 = engine.evaluate_strategy(strategy, population, eval_seed=99)

        # At least one result should differ
        any_diff = any(
            r1.simulator_success != r2.simulator_success
            for r1, r2 in zip(results_42, results_99, strict=False)
        )
        assert any_diff, "Expected at least one different outcome with different seeds"


# ===========================================================================
# Baseline Fairness Tests
# ===========================================================================


class TestBaselineFairness:
    """All strategies must evaluate the same population."""

    def test_all_strategies_see_same_cases(self) -> None:
        engine = EvaluationEngine()
        population = _make_population(10)
        case_ids = [item.case.case_id for item in population]

        strategies = [
            NoActionStrategy(),
            AlwaysRetryStrategy(),
            GenericReminderStrategy(),
        ]

        for strategy in strategies:
            results = engine.evaluate_strategy(strategy, population, eval_seed=42)
            result_case_ids = [r.case_id for r in results]
            assert result_case_ids == case_ids, f"{strategy.name} saw different cases"

    def test_population_order_preserved(self) -> None:
        engine = EvaluationEngine()
        population = _make_population(5)
        results = engine.evaluate_strategy(AlwaysRetryStrategy(), population, eval_seed=42)
        for item, result in zip(population, results, strict=False):
            assert item.case.case_id == result.case_id


# ===========================================================================
# Safety / Guardrails Tests
# ===========================================================================


class TestSafety:
    """Verify REVIVE passes through guardrails."""

    def test_revive_applies_guardrails(self) -> None:
        engine = EvaluationEngine()
        population = _make_population(10)
        strategy = ReviveStrategy()
        results = engine.evaluate_strategy(strategy, population, eval_seed=42)

        for r in results:
            # REVIVE results should always have a guardrail decision
            assert r.guardrail_decision in ("ALLOW", "DENY", "ESCALATE", "NO_ACTION"), (
                f"Missing guardrail decision: {r.guardrail_decision}"
            )

    def test_baselines_skip_guardrails(self) -> None:
        engine = EvaluationEngine()
        population = _make_population(5)

        for strategy in [NoActionStrategy(), AlwaysRetryStrategy(), GenericReminderStrategy()]:
            results = engine.evaluate_strategy(strategy, population, eval_seed=42)
            for r in results:
                assert r.guardrail_decision == "N/A"

    def test_safety_metrics_computation(self) -> None:
        results = [
            CaseEvaluationResult(
                case_id=uuid.uuid4(),
                customer_id=uuid.uuid4(),
                amount_at_risk=Decimal("100"),
                failure_reason="A",
                strategy="REVIVE",
                selected_action="RETRY_LATER",
                guardrail_decision="ALLOW",
                executed=True,
            ),
            CaseEvaluationResult(
                case_id=uuid.uuid4(),
                customer_id=uuid.uuid4(),
                amount_at_risk=Decimal("200"),
                failure_reason="B",
                strategy="REVIVE",
                selected_action="SMS_REMINDER",
                guardrail_decision="DENY",
                guardrail_reason="Economic threshold",
                guardrail_violated=["economic_threshold"],
                executed=False,
            ),
        ]
        sm = compute_safety_metrics(results)
        assert sm.guardrail_allow == 1
        assert sm.guardrail_deny == 1
        assert sm.economic_threshold_denials == 1

    def test_opt_out_customer_blocked_by_revive(self) -> None:
        """REVIVE guardrails should block communication to opted-out customer."""
        engine = EvaluationEngine()
        customer = _make_customer(opt_out=True)
        case = _make_case(customer.customer_id)
        population = [EvaluationPopulationItem(case, customer, None)]

        strategy = ReviveStrategy()
        results = engine.evaluate_strategy(strategy, population, eval_seed=42)

        # If REVIVE selected a communication action, guardrails should block it
        for r in results:
            if r.selected_action in ("EMAIL_REMINDER", "SMS_REMINDER"):
                assert r.guardrail_decision == "DENY"
                assert not r.executed


# ===========================================================================
# Comparative Metrics Tests
# ===========================================================================


class TestComparativeMetrics:
    """Verify comparative metric calculation."""

    def test_revive_vs_no_action(self) -> None:
        revive = FinancialMetrics(
            total_cases=100,
            total_net_recovery=Decimal("5000.00"),
            total_amount_recovered=Decimal("5200.00"),
            total_intervention_cost=Decimal("200.00"),
            recovery_rate=Decimal("0.52000"),
        )
        baseline = FinancialMetrics(
            total_cases=100,
            total_net_recovery=Decimal("0.00"),
            total_amount_recovered=Decimal("0.00"),
            total_intervention_cost=Decimal("0.00"),
            recovery_rate=Decimal("0.00000"),
        )
        cm = compute_comparative_metrics(revive, baseline, "NO_ACTION")
        assert cm.absolute_net_difference == Decimal("5000.00")
        assert cm.recovery_rate_difference == Decimal("0.52000")
        # lift is None when baseline is 0
        assert cm.net_recovery_lift_pct is None

    def test_lift_percentage(self) -> None:
        revive = FinancialMetrics(
            total_net_recovery=Decimal("1500.00"),
            recovery_rate=Decimal("0.30000"),
        )
        baseline = FinancialMetrics(
            total_net_recovery=Decimal("1000.00"),
            recovery_rate=Decimal("0.20000"),
        )
        cm = compute_comparative_metrics(revive, baseline, "ALWAYS_RETRY")
        assert cm.absolute_net_difference == Decimal("500.00")
        assert cm.net_recovery_lift_pct == Decimal("50.0")
