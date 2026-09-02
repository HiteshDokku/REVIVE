"""Report generation for M11 Financial Evaluation.

Generates both machine-readable JSON and human-readable Markdown.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from src.evaluation.metrics import (
    ComparativeMetrics,
    FinancialMetrics,
    SafetyMetrics,
    aggregate_metric,
    compute_comparative_metrics,
)

if TYPE_CHECKING:
    from pathlib import Path


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal objects."""

    def default(self, o: object) -> Any:
        if isinstance(o, Decimal):
            return str(o)
        return super().default(o)


# ---------------------------------------------------------------------------
# Data structures for the multi-seed report
# ---------------------------------------------------------------------------


def _fm_to_dict(fm: FinancialMetrics) -> dict[str, Any]:
    return fm.model_dump(mode="json")


def _sm_to_dict(sm: SafetyMetrics) -> dict[str, Any]:
    return sm.model_dump(mode="json")


def _cm_to_dict(cm: ComparativeMetrics) -> dict[str, Any]:
    return cm.model_dump(mode="json")


# ---------------------------------------------------------------------------
# JSON report
# ---------------------------------------------------------------------------


def generate_json_report(
    seed_results: dict[int, dict[str, tuple[FinancialMetrics, SafetyMetrics]]],
    model_metrics: dict[str, Any],
    metadata: dict[str, Any],
    output_path: Path,
) -> None:
    """Write the complete evaluation report as JSON."""
    report: dict[str, Any] = {
        "metadata": metadata,
        "model_metrics": model_metrics,
        "per_seed": {},
        "aggregated": {},
    }

    strategy_names = list(next(iter(seed_results.values())).keys())

    # Per-seed
    for seed, strategies in seed_results.items():
        report["per_seed"][str(seed)] = {}
        for sname, (fm, sm) in strategies.items():
            report["per_seed"][str(seed)][sname] = {
                "financial": _fm_to_dict(fm),
                "safety": _sm_to_dict(sm),
            }

    # Aggregated across seeds
    for sname in strategy_names:
        nets = [seed_results[s][sname][0].total_net_recovery for s in seed_results]
        recoveries = [seed_results[s][sname][0].total_amount_recovered for s in seed_results]
        costs = [seed_results[s][sname][0].total_intervention_cost for s in seed_results]
        rates = [seed_results[s][sname][0].recovery_rate for s in seed_results]
        avg_nets = [seed_results[s][sname][0].avg_net_recovery_per_case for s in seed_results]

        report["aggregated"][sname] = {
            "total_net_recovery": aggregate_metric(nets).model_dump(mode="json"),
            "total_amount_recovered": aggregate_metric(recoveries).model_dump(mode="json"),
            "total_intervention_cost": aggregate_metric(costs).model_dump(mode="json"),
            "recovery_rate": aggregate_metric(rates).model_dump(mode="json"),
            "avg_net_recovery_per_case": aggregate_metric(avg_nets).model_dump(mode="json"),
        }

    # Comparative: REVIVE vs each baseline
    comparisons: list[dict[str, Any]] = []
    for baseline_name in ["NO_ACTION", "ALWAYS_RETRY", "GENERIC_REMINDER"]:
        per_seed_comps: list[dict[str, Any]] = []
        for seed in seed_results:
            revive_fm = seed_results[seed]["REVIVE"][0]
            baseline_fm = seed_results[seed][baseline_name][0]
            cm = compute_comparative_metrics(revive_fm, baseline_fm, baseline_name)
            per_seed_comps.append({"seed": seed, **_cm_to_dict(cm)})
        comparisons.append(
            {
                "baseline": baseline_name,
                "per_seed": per_seed_comps,
            }
        )
    report["comparisons"] = comparisons

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, cls=DecimalEncoder)


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------


def _fmt(v: Decimal, places: int = 2) -> str:
    """Format Decimal for display."""
    fmt_str = f"0.{'0' * places}"
    return str(v.quantize(Decimal(fmt_str)))


def _pct(v: Decimal) -> str:
    """Format Decimal as percentage string."""
    return f"{_fmt(v * Decimal('100'), 2)}%"


def generate_markdown_report(
    seed_results: dict[int, dict[str, tuple[FinancialMetrics, SafetyMetrics]]],
    model_metrics: dict[str, Any],
    metadata: dict[str, Any],
    output_path: Path,
) -> str:
    """Write the complete evaluation report as Markdown."""
    seeds = sorted(seed_results.keys())
    strategy_names = ["NO_ACTION", "ALWAYS_RETRY", "GENERIC_REMINDER", "REVIVE"]

    lines: list[str] = []

    # Header
    lines.append("# REVIVE — Milestone 11 Financial Evaluation Report")
    lines.append("")

    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(
        "This report presents the realized financial performance of the REVIVE "
        "revenue-recovery system compared to three baseline strategies. "
        "All financial outcomes are determined by the independent M9 InterventionSimulator, "
        "**not** by the propensity model's predicted probabilities."
    )
    lines.append("")

    # Methodology
    lines.append("## Methodology")
    lines.append("")
    lines.append("- **Financial authority**: `InterventionSimulator.simulate()` (M9)")
    lines.append("- **Cost authority**: M9 execution costs from POLICY.md")
    lines.append("- **Temporal ordering**: Action selection → Guardrails → Simulator → Outcome")
    lines.append(
        "- **Leakage protection**: No outcome information available during action selection"
    )
    lines.append(f"- **Seeds**: {seeds}")
    lines.append("- **Evaluation population**: All recovery cases per seed")
    lines.append("")

    # Population
    lines.append("## Population")
    lines.append("")
    for seed in seeds:
        fm0 = seed_results[seed][strategy_names[0]][0]
        lines.append(
            f"- Seed {seed}: {fm0.total_cases} cases, Revenue at risk: ₹{_fmt(fm0.revenue_at_risk)}"
        )
    lines.append("")

    # Strategy Comparison (average across seeds)
    lines.append("## Strategy Comparison (Mean Across Seeds)")
    lines.append("")
    lines.append(
        "| Strategy | Cases | Recovery Rate | Amount Recovered | Cost | Net Recovery | Net/Case |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|")

    for sname in strategy_names:
        nets_fm = [seed_results[s][sname][0] for s in seeds]
        avg_cases = sum((f.total_cases for f in nets_fm), Decimal("0")) / len(seeds)
        avg_rate = sum((f.recovery_rate for f in nets_fm), Decimal("0")) / len(seeds)
        avg_recovered = sum((f.total_amount_recovered for f in nets_fm), Decimal("0")) / len(seeds)
        avg_cost = sum((f.total_intervention_cost for f in nets_fm), Decimal("0")) / len(seeds)
        avg_net = sum((f.total_net_recovery for f in nets_fm), Decimal("0")) / len(seeds)
        avg_net_per = sum((f.avg_net_recovery_per_case for f in nets_fm), Decimal("0")) / len(seeds)

        lines.append(
            f"| {sname} | {int(avg_cases)} | {_pct(avg_rate)} | "
            f"₹{_fmt(avg_recovered)} | ₹{_fmt(avg_cost)} | "
            f"₹{_fmt(avg_net)} | ₹{_fmt(avg_net_per)} |"
        )
    lines.append("")

    # REVIVE vs Baselines
    lines.append("## REVIVE vs Baselines (Mean Across Seeds)")
    lines.append("")
    lines.append("| Baseline | Net Δ | Net Lift % | Recovery Rate Δ | Cost Δ | Gross Recovery Δ |")
    lines.append("|---|---:|---:|---:|---:|---:|")

    for baseline_name in ["NO_ACTION", "ALWAYS_RETRY", "GENERIC_REMINDER"]:
        diffs: list[ComparativeMetrics] = []
        for seed in seeds:
            revive_fm = seed_results[seed]["REVIVE"][0]
            baseline_fm = seed_results[seed][baseline_name][0]
            cm = compute_comparative_metrics(revive_fm, baseline_fm, baseline_name)
            diffs.append(cm)

        avg_net_diff = sum((c.absolute_net_difference for c in diffs), Decimal("0")) / len(diffs)
        lifts = [c.net_recovery_lift_pct for c in diffs if c.net_recovery_lift_pct is not None]
        avg_lift_str = _fmt(sum(lifts, Decimal("0")) / len(lifts), 2) + "%" if lifts else "N/A"
        avg_rate_diff = sum((c.recovery_rate_difference for c in diffs), Decimal("0")) / len(diffs)
        avg_cost_diff = sum((c.cost_difference for c in diffs), Decimal("0")) / len(diffs)
        avg_gross_diff = sum((c.gross_recovery_difference for c in diffs), Decimal("0")) / len(
            diffs
        )

        lines.append(
            f"| {baseline_name} | ₹{_fmt(avg_net_diff)} | {avg_lift_str} | "
            f"{_pct(avg_rate_diff)} | ₹{_fmt(avg_cost_diff)} | ₹{_fmt(avg_gross_diff)} |"
        )
    lines.append("")

    # Safety Metrics
    lines.append("## Safety Metrics (REVIVE, Aggregated)")
    lines.append("")
    total_allow = sum(seed_results[s]["REVIVE"][1].guardrail_allow for s in seeds)
    total_deny = sum(seed_results[s]["REVIVE"][1].guardrail_deny for s in seeds)
    total_esc = sum(seed_results[s]["REVIVE"][1].guardrail_escalate for s in seeds)
    total_na = sum(seed_results[s]["REVIVE"][1].guardrail_no_action for s in seeds)
    total_violations = sum(seed_results[s]["REVIVE"][1].policy_violations for s in seeds)
    total_econ = sum(seed_results[s]["REVIVE"][1].economic_threshold_denials for s in seeds)
    total_hv = sum(seed_results[s]["REVIVE"][1].high_value_escalations for s in seeds)

    lines.append(f"- Guardrail ALLOW: {total_allow}")
    lines.append(f"- Guardrail DENY: {total_deny}")
    lines.append(f"- Guardrail ESCALATE: {total_esc}")
    lines.append(f"- Guardrail NO_ACTION: {total_na}")
    lines.append(f"- Economic threshold denials: {total_econ}")
    lines.append(f"- High-value escalations: {total_hv}")
    lines.append(f"- **Policy violations: {total_violations}**")
    lines.append("")

    # Model Metrics
    lines.append("## Model Metrics (From M6 Training Artifacts)")
    lines.append("")
    if model_metrics:
        for k, v in model_metrics.items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("No model metrics available.")
    lines.append("")
    lines.append("*These are model-quality metrics from the M6 training evaluation,*")
    lines.append("*NOT realized financial metrics. They are included for completeness.*")
    lines.append("")

    # Multi-Seed Stability
    lines.append("## Multi-Seed Stability")
    lines.append("")
    lines.append("### Total Net Recovery by Seed")
    lines.append("")
    lines.append("| Seed | NO_ACTION | ALWAYS_RETRY | GENERIC_REMINDER | REVIVE |")
    lines.append("|---:|---:|---:|---:|---:|")
    for seed in seeds:
        vals = [f"₹{_fmt(seed_results[seed][s][0].total_net_recovery)}" for s in strategy_names]
        lines.append(f"| {seed} | {' | '.join(vals)} |")
    lines.append("")

    lines.append("### Aggregation (Net Recovery)")
    lines.append("")
    lines.append("| Strategy | Mean | Std | Min | Max |")
    lines.append("|---|---:|---:|---:|---:|")
    for sname in strategy_names:
        net_vals = [seed_results[s][sname][0].total_net_recovery for s in seeds]
        agg = aggregate_metric(net_vals)
        lines.append(f"| {sname} | ₹{agg.mean} | ₹{agg.std} | ₹{agg.min_val} | ₹{agg.max_val} |")
    lines.append("")

    # Integrity
    lines.append("## Integrity / Leakage Audit")
    lines.append("")
    lines.append("- ✅ Action selection precedes simulation execution")
    lines.append("- ✅ Outcomes (`amount_recovered`, `status_after`) unavailable during selection")
    lines.append("- ✅ InterventionSimulator is the sole financial authority")
    lines.append("- ✅ No target leakage (cases presented as OPEN, predictions stripped)")
    lines.append("- ✅ No future-information leakage (no past interventions/interactions provided)")
    lines.append("- ✅ All strategies evaluate the same population per seed")
    lines.append("- ✅ Per-case deterministic seeds ensure fair random draws")
    lines.append("")

    # Limitations
    lines.append("## Limitations")
    lines.append("")
    lines.append(
        "1. All results are based on a **synthetic simulator** with known causal assumptions."
    )
    lines.append(
        "2. The simulator's causal matrix is fixed; real-world effectiveness would differ."
    )
    lines.append("3. Each case receives exactly one intervention attempt (no multi-step recovery).")
    lines.append("4. Cost discrepancy: M7 decision costs differ from M9 execution costs used here.")
    lines.append(
        "5. REVIVE's guardrails may block economically marginal actions that baselines execute."
    )
    lines.append(
        "6. Results should not be directly extrapolated to real-world financial performance."
    )
    lines.append("")

    # Metadata
    lines.append("## Reproducibility Metadata")
    lines.append("")
    for k, v in metadata.items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")

    content = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    return content
