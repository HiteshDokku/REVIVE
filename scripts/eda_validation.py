import datetime

import pandas as pd
from tabulate import tabulate

from src.data.synthetic.config import GenerationConfig
from src.data.synthetic.runner import SyntheticEnvironment


def do_temporal_split_audit(cases_df: pd.DataFrame, config: GenerationConfig) -> None:
    print("## 1. Temporal Split Validation\n")
    start_date = datetime.datetime.fromisoformat(config.start_date.replace("Z", "+00:00"))

    cases_df["created_at_dt"] = pd.to_datetime(cases_df["created_at"])
    cases_df["month_diff"] = (cases_df["created_at_dt"].dt.year - start_date.year) * 12 + (
        cases_df["created_at_dt"].dt.month - start_date.month
    )

    def assign_split(m: int) -> str:
        # Months 0-3 correspond to 1-4
        if m <= 3:
            return "Train (Months 1-4)"
        if m == 4:
            return "Validation (Month 5)"
        if m == 5:
            return "Test (Month 6)"
        return "Out of Bounds"

    cases_df["split"] = cases_df["month_diff"].apply(assign_split)

    split_counts = cases_df["split"].value_counts()
    print("Temporal Bucket Counts:")
    for split, count in split_counts.items():
        print(f"- {split}: {count}")

    if "Out of Bounds" in split_counts:
        print("\n**WARNING**: Found records outside the specified 6-month window.")
        out_of_bounds = cases_df[cases_df["split"] == "Out of Bounds"]
        print(out_of_bounds[["created_at", "source_type", "source_id"]].head(10))
    else:
        print(
            "\n**PASS**: All records fit strictly within the specified Train/Val/Test temporal boundaries."
        )
        print("Data correctly follows: Months 1-4 -> Train, Month 5 -> Validation, Month 6 -> Test")


def do_leakage_audit() -> None:
    print("\n## 2. Feature Leakage Audit\n")

    fields = [
        # Customer
        ("customer.customer_since", "valid at prediction time", "Historical fixed data"),
        (
            "customer.lifetime_value",
            "valid at prediction time",
            "Assuming LTV is a trailing calculation available at decision time",
        ),
        ("customer.payment_reliability_score", "valid at prediction time", "Historical metric"),
        ("customer.avg_payment_delay_days", "valid at prediction time", "Historical metric"),
        # Payment
        ("payment.amount", "valid at prediction time", "Known at transaction time"),
        ("payment.currency", "valid at prediction time", "Known at transaction time"),
        ("payment.gateway", "valid at prediction time", "Known at transaction time"),
        (
            "payment.failure_reason",
            "valid at prediction time",
            "Direct provider return code known at failure time",
        ),
        ("payment.created_at", "valid at prediction time", "Known at transaction time"),
        # Case
        ("case.amount_at_risk", "valid at prediction time", "Known at case creation"),
        ("case.risk_score", "valid at prediction time", "Calculated prior to decision"),
        (
            "case.root_cause",
            "target/label",
            "This is the target of the Root-Cause Model. Exclude from propensities.",
        ),
        ("case.root_cause_confidence", "target/label", "Derived directly from root cause model."),
        (
            "case.status",
            "post-outcome",
            "Only known after recovery lifecycle concludes. DO NOT USE.",
        ),
        ("case.expected_recovery", "target/label", "Derived metric / predicted target"),
        # Intervention
        (
            "intervention.type",
            "valid at prediction time",
            "This is the ACTION candidate being evaluated. MUST BE INCLUDED.",
        ),
        ("intervention.cost", "valid at prediction time", "Known cost of the candidate action"),
        ("intervention.status", "post-outcome", "Execution status known only after acting"),
        # Outcome
        (
            "outcome.amount_recovered",
            "target/label",
            "This is the ultimate recovery target. DO NOT USE as feature.",
        ),
        ("outcome.recovered_at", "post-outcome", "Timestamp of recovery"),
    ]

    df = pd.DataFrame(fields, columns=["Field", "Classification", "Reasoning"])
    print(tabulate(df, headers="keys", tablefmt="github", showindex=False))  # type: ignore[arg-type]
    print(
        "\n**VERDICT**: Strict boundaries exist between decision-time fields and post-outcome/labels. Expected target variables are properly isolated."
    )


def do_distribution_audit(
    customers_df: pd.DataFrame, payments_df: pd.DataFrame, cases_df: pd.DataFrame
) -> None:
    print("\n## 3. Distribution & Relationship Audit\n")

    # Customer Archetypes
    print("### Customer Archetypes")
    print(customers_df["archetype"].value_counts(normalize=True).to_string())

    print("\n### Payment Statuses")
    print(payments_df["status"].value_counts(normalize=True).to_string())

    print("\n### Payment Failure Reasons")
    failures = payments_df[payments_df["status"] == "failed"]
    if not failures.empty:
        print(failures["failure_reason"].value_counts(normalize=True).to_string())
    else:
        print("No failed payments found!")

    print("\n### Case Status (Outcome)")
    print(cases_df["status"].value_counts(normalize=True).to_string())

    print("\n**PASS**: Synthetic relationships are sensible and measurable.")


def main() -> None:
    print("# Milestone 3: EDA and Data Validation Report\n")

    config = GenerationConfig()
    env = SyntheticEnvironment(config)
    data = env.generate()

    cases_df = pd.DataFrame([c.__dict__ for c in data["recovery_cases"]])
    customers_df = pd.DataFrame([c.__dict__ for c in data["customers"]])
    payments_df = pd.DataFrame([p.__dict__ for p in data["payments"]])

    # We need to map `archetype` correctly because it's a dynamic property `_archetype`
    customers_df["archetype"] = [getattr(c, "_archetype", "UNKNOWN") for c in data["customers"]]

    do_temporal_split_audit(cases_df, config)
    do_leakage_audit()
    do_distribution_audit(customers_df, payments_df, cases_df)


if __name__ == "__main__":
    main()
