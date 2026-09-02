"""M11 Financial Evaluation — Reproducible multi-seed comparison script.

Usage:
    .venv\\Scripts\\python.exe scripts/evaluate_financials.py

Evaluates four strategies (NO_ACTION, ALWAYS_RETRY, GENERIC_REMINDER, REVIVE)
across multiple seeds using the M9 InterventionSimulator as the sole
financial authority.

No models are retrained. No simulator logic is modified.
"""

from __future__ import annotations

import json
import platform
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.data.synthetic.config import GenerationConfig  # noqa: E402
from src.data.synthetic.runner import SyntheticEnvironment  # noqa: E402
from src.evaluation.engine import (  # noqa: E402
    EXECUTION_COSTS,
    EvaluationEngine,
    prepare_evaluation_population,
)
from src.evaluation.metrics import (  # noqa: E402
    FinancialMetrics,
    SafetyMetrics,
    compute_financial_metrics,
    compute_safety_metrics,
)
from src.evaluation.report import generate_json_report, generate_markdown_report  # noqa: E402
from src.evaluation.strategies import (  # noqa: E402
    AlwaysRetryStrategy,
    GenericReminderStrategy,
    NoActionStrategy,
    ReviveStrategy,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_SEEDS = [42, 43]
NUM_CUSTOMERS = 500
NUM_MONTHS = 6


def load_model_metrics() -> dict[str, Any]:
    """Load M6 model metrics from the trained artifact, if available."""
    metadata_path = PROJECT_ROOT / "artifacts" / "models" / "recovery_model_metadata.json"
    if metadata_path.exists():
        with open(metadata_path, encoding="utf-8") as f:
            meta = json.load(f)
        return dict(meta.get("metrics", {}))
    return {}


def run_single_seed(
    seed: int,
    engine: EvaluationEngine,
    strategies: list[Any],
) -> dict[str, tuple[FinancialMetrics, SafetyMetrics, int]]:
    """Run all strategies on a single seed.

    Returns: {strategy_name: (FinancialMetrics, SafetyMetrics, num_cases)}
    """
    print(f"\n{'=' * 60}")
    print(f"  SEED {seed}")
    print(f"{'=' * 60}")

    # 1. Generate synthetic data with this seed
    config = GenerationConfig(
        num_customers=NUM_CUSTOMERS,
        num_months=NUM_MONTHS,
        seed=seed,
    )
    env = SyntheticEnvironment(config)
    data = env.generate()

    # 2. Prepare evaluation population (same for ALL strategies)
    population = prepare_evaluation_population(data)
    num_cases = len(population)
    print(f"  Population: {num_cases} recovery cases")

    revenue_at_risk = sum((item.case.amount_at_risk for item in population), Decimal("0.00"))
    print(f"  Revenue at risk: ₹{revenue_at_risk:,.2f}")

    # 3. Evaluate each strategy on the SAME population
    results: dict[str, tuple[FinancialMetrics, SafetyMetrics, int]] = {}

    for strategy in strategies:
        t0 = time.time()
        case_results = engine.evaluate_strategy(strategy, population, seed)
        elapsed = time.time() - t0

        fm = compute_financial_metrics(case_results)
        sm = compute_safety_metrics(case_results)
        results[strategy.name] = (fm, sm, num_cases)

        print(
            f"  {strategy.name:20s} | "
            f"Net: ₹{fm.total_net_recovery:>12,.2f} | "
            f"Rate: {float(fm.recovery_rate) * 100:>6.2f}% | "
            f"Cost: ₹{fm.total_intervention_cost:>10,.2f} | "
            f"{elapsed:.1f}s"
        )

    return results


def main() -> None:
    """Run the complete M11 financial evaluation."""
    start_time = datetime.now(UTC)
    print("=" * 60)
    print("  REVIVE — Milestone 11 Financial Evaluation")
    print("=" * 60)
    print(f"  Started: {start_time.isoformat()}")
    print(f"  Seeds: {DEFAULT_SEEDS}")
    print(f"  Scale: {NUM_CUSTOMERS} customers x {NUM_MONTHS} months")
    print("  Cost source: M9 execution costs (POLICY.md)")
    print()

    # Initialize strategies
    strategies = [
        NoActionStrategy(),
        AlwaysRetryStrategy(),
        GenericReminderStrategy(),
        ReviveStrategy(),
    ]

    engine = EvaluationEngine()

    # Run evaluation across all seeds
    seed_results: dict[int, dict[str, tuple[FinancialMetrics, SafetyMetrics]]] = {}

    for seed in DEFAULT_SEEDS:
        raw = run_single_seed(seed, engine, strategies)
        seed_results[seed] = {sname: (fm, sm) for sname, (fm, sm, _nc) in raw.items()}

    # Load model metrics
    model_metrics = load_model_metrics()

    # Build metadata
    end_time = datetime.now(UTC)
    metadata: dict[str, Any] = {
        "evaluation_timestamp": end_time.isoformat(),
        "seeds": DEFAULT_SEEDS,
        "num_customers_per_seed": NUM_CUSTOMERS,
        "num_months": NUM_MONTHS,
        "cost_source": "M9 execution costs (POLICY.md)",
        "cost_table": {k: str(v) for k, v in EXECUTION_COSTS.items()},
        "strategies": [s.name for s in strategies],
        "simulator": "src.simulator.engine.InterventionSimulator",
        "evaluation_engine": "src.evaluation.engine.EvaluationEngine",
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "duration_seconds": (end_time - start_time).total_seconds(),
    }

    # Generate reports
    json_path = PROJECT_ROOT / "artifacts" / "evaluations" / "m11_financial_report.json"
    md_path = PROJECT_ROOT / "artifacts" / "evaluations" / "m11_financial_report.md"

    generate_json_report(seed_results, model_metrics, metadata, json_path)
    print(f"\n  JSON report: {json_path}")

    generate_markdown_report(seed_results, model_metrics, metadata, md_path)
    print(f"  Markdown report: {md_path}")

    # Final summary
    print("\n" + "=" * 60)
    print("  FINAL SUMMARY")
    print("=" * 60)

    for sname in ["NO_ACTION", "ALWAYS_RETRY", "GENERIC_REMINDER", "REVIVE"]:
        nets = [seed_results[s][sname][0].total_net_recovery for s in DEFAULT_SEEDS]
        avg_net = sum(nets, Decimal("0")) / len(nets)
        print(f"  {sname:20s} | Mean Net Recovery: ₹{avg_net:>12,.2f}")

    # Safety check
    total_violations = sum(seed_results[s]["REVIVE"][1].policy_violations for s in DEFAULT_SEEDS)
    print(f"\n  REVIVE policy violations: {total_violations}")
    if total_violations == 0:
        print("  ✅ Zero policy violations")
    else:
        print("  ⚠️  Policy violations detected — investigate!")

    print(f"\n  Duration: {metadata['duration_seconds']:.1f}s")
    print("  Done.")


if __name__ == "__main__":
    main()
