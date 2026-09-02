"""Financial, safety, and comparative metric computation for M11.

All monetary calculations use Decimal. Rounding is deferred to reporting only.
"""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from src.evaluation.engine import CaseEvaluationResult


# ---------------------------------------------------------------------------
# Metric models
# ---------------------------------------------------------------------------
class FinancialMetrics(BaseModel):
    """Realized financial metrics for a single strategy + seed."""

    total_cases: int = 0
    successful_recoveries: int = 0
    recovery_rate: Decimal = Decimal("0.00000")
    revenue_at_risk: Decimal = Decimal("0.00")
    total_amount_recovered: Decimal = Decimal("0.00")
    total_intervention_cost: Decimal = Decimal("0.00")
    total_net_recovery: Decimal = Decimal("0.00")
    avg_recovery_per_case: Decimal = Decimal("0.00")
    avg_cost_per_case: Decimal = Decimal("0.00")
    avg_net_recovery_per_case: Decimal = Decimal("0.00")
    total_interventions: int = 0
    total_no_action: int = 0


class SafetyMetrics(BaseModel):
    """Guardrail and policy safety metrics."""

    guardrail_allow: int = 0
    guardrail_deny: int = 0
    guardrail_escalate: int = 0
    guardrail_no_action: int = 0
    guardrail_na: int = 0
    # Detailed deny reasons
    retry_limit_blocks: int = 0
    contact_limit_blocks: int = 0
    cooldown_blocks: int = 0
    recovery_window_blocks: int = 0
    opt_out_blocks: int = 0
    already_resolved_blocks: int = 0
    high_value_escalations: int = 0
    economic_threshold_denials: int = 0
    # Policy violations (target: 0)
    policy_violations: int = 0


class ComparativeMetrics(BaseModel):
    """REVIVE vs a single baseline comparison."""

    baseline_name: str
    revive_net_recovery: Decimal = Decimal("0.00")
    baseline_net_recovery: Decimal = Decimal("0.00")
    absolute_net_difference: Decimal = Decimal("0.00")
    net_recovery_lift_pct: Decimal | None = None
    revive_recovery_rate: Decimal = Decimal("0.00000")
    baseline_recovery_rate: Decimal = Decimal("0.00000")
    recovery_rate_difference: Decimal = Decimal("0.00000")
    cost_difference: Decimal = Decimal("0.00")
    gross_recovery_difference: Decimal = Decimal("0.00")


class AggregatedMetric(BaseModel):
    """Multi-seed aggregation of a single metric."""

    mean: Decimal = Decimal("0.00")
    std: Decimal = Decimal("0.00")
    min_val: Decimal = Decimal("0.00")
    max_val: Decimal = Decimal("0.00")


# ---------------------------------------------------------------------------
# Computation functions
# ---------------------------------------------------------------------------


def compute_financial_metrics(
    results: list[CaseEvaluationResult],
) -> FinancialMetrics:
    """Compute realized financial metrics from case evaluation results."""
    total_cases = len(results)
    if total_cases == 0:
        return FinancialMetrics()

    successful = sum(1 for r in results if r.simulator_success is True)
    revenue_at_risk = sum((r.amount_at_risk for r in results), Decimal("0.00"))
    total_recovered = sum((r.amount_recovered for r in results), Decimal("0.00"))
    total_cost = sum((r.action_cost for r in results), Decimal("0.00"))
    total_net = sum((r.net_recovery for r in results), Decimal("0.00"))
    total_interventions = sum(1 for r in results if r.executed)
    total_no_action = sum(1 for r in results if r.selected_action == "NO_ACTION" or not r.executed)

    tc = Decimal(str(total_cases))
    recovery_rate = (total_recovered / revenue_at_risk) if revenue_at_risk > 0 else Decimal("0")

    return FinancialMetrics(
        total_cases=total_cases,
        successful_recoveries=successful,
        recovery_rate=recovery_rate,
        revenue_at_risk=revenue_at_risk,
        total_amount_recovered=total_recovered,
        total_intervention_cost=total_cost,
        total_net_recovery=total_net,
        avg_recovery_per_case=total_recovered / tc,
        avg_cost_per_case=total_cost / tc,
        avg_net_recovery_per_case=total_net / tc,
        total_interventions=total_interventions,
        total_no_action=total_no_action,
    )


def compute_safety_metrics(
    results: list[CaseEvaluationResult],
) -> SafetyMetrics:
    """Compute guardrail and safety metrics from case evaluation results."""
    metrics = SafetyMetrics()

    for r in results:
        gd = r.guardrail_decision
        if gd == "ALLOW":
            metrics.guardrail_allow += 1
        elif gd == "DENY":
            metrics.guardrail_deny += 1
        elif gd == "ESCALATE":
            metrics.guardrail_escalate += 1
        elif gd == "NO_ACTION":
            metrics.guardrail_no_action += 1
        else:
            metrics.guardrail_na += 1

        # Classify deny/escalate reasons
        for violated in r.guardrail_violated:
            if violated == "retry_limit":
                metrics.retry_limit_blocks += 1
            elif violated == "contact_limit":
                metrics.contact_limit_blocks += 1
            elif violated == "cooldown":
                metrics.cooldown_blocks += 1
            elif violated == "recovery_window":
                metrics.recovery_window_blocks += 1
            elif violated == "customer_opt_out":
                metrics.opt_out_blocks += 1
            elif violated == "already_resolved":
                metrics.already_resolved_blocks += 1
            elif violated == "high_value_escalation":
                metrics.high_value_escalations += 1
            elif violated == "economic_threshold":
                metrics.economic_threshold_denials += 1

    return metrics


def compute_comparative_metrics(
    revive: FinancialMetrics,
    baseline: FinancialMetrics,
    baseline_name: str,
) -> ComparativeMetrics:
    """Compute REVIVE vs baseline comparison."""
    net_diff = revive.total_net_recovery - baseline.total_net_recovery
    lift: Decimal | None = None
    if baseline.total_net_recovery != Decimal("0"):
        lift = (net_diff / abs(baseline.total_net_recovery)) * Decimal("100")

    return ComparativeMetrics(
        baseline_name=baseline_name,
        revive_net_recovery=revive.total_net_recovery,
        baseline_net_recovery=baseline.total_net_recovery,
        absolute_net_difference=net_diff,
        net_recovery_lift_pct=lift,
        revive_recovery_rate=revive.recovery_rate,
        baseline_recovery_rate=baseline.recovery_rate,
        recovery_rate_difference=revive.recovery_rate - baseline.recovery_rate,
        cost_difference=revive.total_intervention_cost - baseline.total_intervention_cost,
        gross_recovery_difference=revive.total_amount_recovered - baseline.total_amount_recovered,
    )


def aggregate_metric(values: list[Decimal]) -> AggregatedMetric:
    """Compute mean, std, min, max for a list of Decimal values."""
    if not values:
        return AggregatedMetric()

    n = Decimal(str(len(values)))
    mean = sum(values, Decimal("0")) / n
    min_val = min(values)
    max_val = max(values)

    if len(values) > 1:
        variance = sum((v - mean) ** 2 for v in values) / (n - Decimal("1"))
        std = Decimal(str(math.sqrt(float(variance))))
    else:
        std = Decimal("0")

    return AggregatedMetric(
        mean=mean.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        std=std.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        min_val=min_val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        max_val=max_val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
    )
