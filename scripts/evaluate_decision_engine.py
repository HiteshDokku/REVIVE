"""Script to evaluate the Economic Decision Engine against M6 holdout."""

import time
from decimal import Decimal

import pandas as pd

from src.data.synthetic.config import GenerationConfig
from src.data.synthetic.runner import SyntheticEnvironment
from src.database.models import Customer, Payment, RecoveryCase
from src.decision.cost import ActionCostModel
from src.decision.policy import ExpectedValuePolicy
from src.models.recovery_propensity import RecoveryPropensityModel


def load_m6_data() -> tuple[list[tuple[RecoveryCase, Customer, Payment]], pd.DataFrame]:
    """Load month-6 data from the synthetic generator without leaking to inference."""
    # Generate data using the exact same seed as training
    config = GenerationConfig(seed=42)
    env = SyntheticEnvironment(config)
    data = env.generate()

    # In-memory mapping of lists to pseudo-SQLAlchemy objects
    cases = data["recovery_cases"]
    customers_dict = {c.customer_id: c for c in data["customers"]}
    payments_dict = {p.payment_id: p for p in data["payments"]}

    df_data = []
    objects = []

    for case in cases:
        customer = customers_dict.get(case.customer_id)
        payment = payments_dict.get(case.source_id)  # trigger payment

        if not customer or not payment:
            continue

        objects.append((case, customer, payment))

        # True outcome evaluation info (OFFLINE ONLY)
        df_data.append(
            {
                "case_id": str(case.case_id),
                "amount": float(case.amount_at_risk),
                "actual_action": case.interventions[0].action_type
                if case.interventions
                else "NO_ACTION",
                "actual_outcome": 1 if case.status == "RECOVERED" else 0,
                "created_at": case.created_at,
            }
        )

    df = pd.DataFrame(df_data)
    df = df.sort_values("created_at")

    # Take the last 10% as M6 to be consistent with the train script methodology
    m6_idx = int(len(df) * 0.9)
    m6_df = df.iloc[m6_idx:].copy()
    m6_objects = objects[m6_idx:]

    return m6_objects, m6_df


def main() -> None:
    print("=" * 70)
    print("REVIVE Decision Engine Evaluation (M6 Holdout)")
    print("=" * 70)

    start_time = time.time()

    print("Loading M6 data...")
    m6_objects, m6_df = load_m6_data()
    print(f"Loaded {len(m6_objects)} cases.")

    # Initialize engine
    cost_model = ActionCostModel()
    propensity_model = RecoveryPropensityModel()
    policy = ExpectedValuePolicy(propensity_model=propensity_model)

    # Tracking
    results = []

    # We also want to compute what happens if we use baselines.
    # But note: we only know the true outcome of the action that was ACTUALLY taken in history.
    # We cannot perfectly know the true outcome if a policy chooses a different action.
    # Therefore, "Total Expected Net Recovery" is exactly what we must measure for the policy lift!

    print("Evaluating policies...")
    for idx, (case, customer, payment) in enumerate(m6_objects):
        if idx % 1000 == 0:
            print(f"Processed {idx}/{len(m6_objects)}...")

        # REVIVE Policy
        decision = policy.evaluate(case, customer, trigger_payment=payment)

        # Baselines Expected Value
        # 1. NO_ACTION
        na_ev = Decimal("0.00")

        # 2. ALWAYS_RETRY
        retry_ev = Decimal("0.00")
        retry_action = next(
            (a for a in decision.ranked_actions if a.action_type == "RETRY_LATER"), None
        )
        if retry_action and retry_action.is_eligible:
            retry_ev = retry_action.expected_net_recovery

        # 3. GENERIC_REMINDER (Email)
        email_ev = Decimal("0.00")
        email_action = next(
            (a for a in decision.ranked_actions if a.action_type == "EMAIL_REMINDER"), None
        )
        if email_action and email_action.is_eligible:
            email_ev = email_action.expected_net_recovery

        # 4. Actual Historical (Oracle mapping)
        # We find what the expected value was for the action *actually* taken historically.
        actual_action_type = m6_df.iloc[idx]["actual_action"]
        hist_ev = Decimal("0.00")
        hist_action = next(
            (a for a in decision.ranked_actions if a.action_type == actual_action_type), None
        )
        if hist_action:
            hist_ev = hist_action.expected_net_recovery

        results.append(
            {
                "case_id": decision.case_id,
                "revive_action": decision.selected_action,
                "revive_ev": float(decision.expected_net_recovery),
                "no_action_ev": float(na_ev),
                "always_retry_ev": float(retry_ev),
                "generic_reminder_ev": float(email_ev),
                "historical_ev": float(hist_ev),
                "amount_at_risk": float(case.amount_at_risk),
                "actual_historical_outcome": m6_df.iloc[idx]["actual_outcome"],
                "actual_historical_action": actual_action_type,
                "actual_historical_cost": float(cost_model.get_cost(actual_action_type))
                if actual_action_type != "NO_ACTION"
                else 0.0,
            }
        )

    results_df = pd.DataFrame(results)

    print("\n" + "=" * 70)
    print("RESULTS (Expected / Model-Based Metrics)")
    print("=" * 70)

    total_cases = len(results_df)

    # REVIVE
    revive_total_ev = results_df["revive_ev"].sum()
    revive_avg_ev = revive_total_ev / total_cases
    revive_no_action_rate = (results_df["revive_action"] == "NO_ACTION").mean()

    # Baselines
    na_total_ev = results_df["no_action_ev"].sum()
    retry_total_ev = results_df["always_retry_ev"].sum()
    email_total_ev = results_df["generic_reminder_ev"].sum()
    hist_total_ev = results_df["historical_ev"].sum()

    print(f"Total Cases Evaluated: {total_cases:,}")
    print("\nTotal Expected Net Recovery:")
    print(f"1. NO_ACTION Baseline:        ${na_total_ev:,.2f}")
    print(f"2. ALWAYS_RETRY Baseline:     ${retry_total_ev:,.2f}")
    print(f"3. GENERIC_REMINDER Baseline: ${email_total_ev:,.2f}")
    print(f"4. HISTORICAL Policy:         ${hist_total_ev:,.2f}")
    print(f"5. REVIVE ExpectedValuePolicy:${revive_total_ev:,.2f}")

    print("\nIncremental Expected Net Recovery (REVIVE vs Baselines):")
    print(f"vs NO_ACTION:        +${revive_total_ev - na_total_ev:,.2f}")
    print(
        f"vs ALWAYS_RETRY:     +${revive_total_ev - retry_total_ev:,.2f} ({((revive_total_ev - retry_total_ev) / max(1, retry_total_ev)):.2%})"
    )
    print(
        f"vs GENERIC_REMINDER: +${revive_total_ev - email_total_ev:,.2f} ({((revive_total_ev - email_total_ev) / max(1, email_total_ev)):.2%})"
    )
    print(
        f"vs HISTORICAL:       +${revive_total_ev - hist_total_ev:,.2f} ({((revive_total_ev - hist_total_ev) / max(1, hist_total_ev)):.2%})"
    )

    print(f"\nREVIVE Average Expected Net Recovery per Case: ${revive_avg_ev:.2f}")
    print(f"REVIVE NO_ACTION Selection Rate: {revive_no_action_rate:.2%}")

    print("\nREVIVE Action Distribution:")
    action_counts = results_df["revive_action"].value_counts(normalize=True)
    for action, pct in action_counts.items():
        print(f"  {action}: {pct:.2%}")

    print("\n" + "=" * 70)
    print("RESULTS (Realized / Holdout Historical Outcomes)")
    print("=" * 70)
    # The realized outcomes only exist for the HISTORICAL policy (the actual action taken).
    # We cannot measure realized outcomes for REVIVE unless REVIVE coincidentally chose the historical action.
    # We will compute the realized net recovery for the historical dataset as an upper-bound sanity check.

    realized_recovery = (
        results_df["actual_historical_outcome"] * results_df["amount_at_risk"]
    ).sum()
    realized_cost = results_df["actual_historical_cost"].sum()
    realized_net = realized_recovery - realized_cost

    print(f"Historical Realized Recovery:      ${realized_recovery:,.2f}")
    print(f"Historical Realized Cost:          ${realized_cost:,.2f}")
    print(f"Historical Realized Net Recovery:  ${realized_net:,.2f}")

    # How well did our model estimate the historical realized net recovery?
    estimation_error = abs(hist_total_ev - realized_net)
    print(
        f"\nModel Estimation Error of Historical Value: ${estimation_error:,.2f} ({(estimation_error / realized_net):.2%})"
    )

    print(f"\nEvaluation complete in {time.time() - start_time:.1f}s.")


if __name__ == "__main__":
    main()
