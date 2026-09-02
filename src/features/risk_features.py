from typing import Any

import pandas as pd

from src.database.models import Customer, Payment, RecoveryCase


class RiskFeatureExtractor:
    """Extracts features for the Revenue Risk Model ensuring strict point-in-time correctness."""

    def __init__(
        self, customers: list[Customer], payments: list[Payment], cases: list[RecoveryCase]
    ):
        self.customers_map = {c.customer_id: c for c in customers}
        # Only keep payments that occurred before the case to prevent leakage, but we can't do that globally.
        # We store them all and filter per-case during extraction.
        self.payments = payments
        self.cases = cases

        # Pre-group payments by customer for faster historical lookups
        self.cust_payments: dict[Any, list[Payment]] = {}
        for p in self.payments:
            if p.customer_id not in self.cust_payments:
                self.cust_payments[p.customer_id] = []
            self.cust_payments[p.customer_id].append(p)

        # Pre-group cases by customer
        self.cust_cases: dict[Any, list[RecoveryCase]] = {}
        for c in self.cases:
            if c.customer_id not in self.cust_cases:
                self.cust_cases[c.customer_id] = []
            self.cust_cases[c.customer_id].append(c)

    def extract_features(self, case: RecoveryCase) -> dict[str, Any]:
        """Extract features available exactly at the time the case was created."""
        customer = self.customers_map[case.customer_id]

        # We need the triggering payment, if applicable
        trigger_payment = None
        if case.source_type == "payment":
            trigger_payment = next(
                (
                    p
                    for p in self.cust_payments.get(case.customer_id, [])
                    if p.payment_id == case.source_id
                ),
                None,
            )

        # Temporal bounds: strictly before the case was created
        past_payments = [
            p
            for p in self.cust_payments.get(case.customer_id, [])
            if p.created_at < case.created_at
        ]
        past_cases = [
            c for c in self.cust_cases.get(case.customer_id, []) if c.created_at < case.created_at
        ]

        features: dict[str, Any] = {}

        # 1. Transaction Features
        features["amount"] = float(case.amount_at_risk)
        features["hour"] = case.created_at.hour
        features["weekday"] = case.created_at.weekday()
        features["day_of_month"] = case.created_at.day

        if trigger_payment:
            features["payment_method"] = trigger_payment.payment_method
            features["gateway"] = trigger_payment.gateway or "UNKNOWN"
            features["failure_code"] = trigger_payment.failure_code or "UNKNOWN"
            features["failure_reason"] = trigger_payment.failure_reason or "UNKNOWN"
        else:
            features["payment_method"] = "UNKNOWN"
            features["gateway"] = "UNKNOWN"
            features["failure_code"] = "UNKNOWN"
            features["failure_reason"] = "UNKNOWN"

        # 2. Customer Features
        features["customer_age_days"] = max(
            0, (case.created_at.date() - customer.customer_since.date()).days
        )
        features["active_subscriptions"] = customer.active_subscriptions
        features["lifetime_value"] = float(customer.lifetime_value)
        features["payment_reliability_score"] = float(customer.payment_reliability_score or 0.0)
        features["avg_payment_delay_days"] = float(customer.avg_payment_delay_days or 0.0)

        # Historical payment success rate (calculated dynamically to prevent leakage)
        if len(past_payments) > 0:
            success_count = sum(1 for p in past_payments if p.status == "successful")
            features["historical_success_rate"] = success_count / len(past_payments)
            features["failure_count"] = len(past_payments) - success_count
        else:
            features["historical_success_rate"] = 1.0
            features["failure_count"] = 0

        # 3. History Features
        # Failures in last 30 days
        cutoff_30d = case.created_at - pd.Timedelta(days=30)
        recent_payments = [p for p in past_payments if p.created_at >= cutoff_30d]
        features["failures_last_30d"] = sum(1 for p in recent_payments if p.status == "failed")

        # Prior recovery rate
        past_closed_cases = [
            c
            for c in past_cases
            if c.status in ("RECOVERED", "CLOSED") and c.updated_at < case.created_at
        ]
        if len(past_closed_cases) > 0:
            recovered_count = sum(1 for c in past_closed_cases if c.status == "RECOVERED")
            features["prior_recovery_rate"] = recovered_count / len(past_closed_cases)
        else:
            features["prior_recovery_rate"] = 0.5  # Neutral prior

        # 4. Context Features
        features["current_retry_count"] = 0  # 0 at prediction time initially
        features["intervention_count"] = 0  # 0 before any interventions

        return features

    def extract_all(self, target_cases: list[RecoveryCase]) -> pd.DataFrame:
        """Extract features for a batch of cases and return as a DataFrame."""
        rows = []
        for case in target_cases:
            feat = self.extract_features(case)
            # Label extraction: 1 if RECOVERED, 0 if CLOSED (or other)
            # Assuming we only train on cases that have reached a terminal state in the synthetic data
            feat["label"] = 1 if case.status == "RECOVERED" else 0
            # Metadata for splits
            feat["case_id"] = str(case.case_id)
            feat["created_at"] = case.created_at
            rows.append(feat)

        return pd.DataFrame(rows)
