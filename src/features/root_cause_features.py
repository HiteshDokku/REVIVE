"""Feature extractor for the Root-Cause ML Model."""

import bisect
import math
from typing import Any

import pandas as pd

from src.database.models import Customer, Payment, RecoveryCase


class RootCauseFeatureExtractor:
    """Extracts point-in-time safe features for Root-Cause classification."""

    def __init__(
        self, customers: list[Customer], payments: list[Payment], cases: list[RecoveryCase]
    ):
        self.customers_map = {c.customer_id: c for c in customers}
        self.payments = payments
        self.cases = cases

        # Group payments by customer
        self.cust_payments: dict[Any, list[Payment]] = {}
        for p in self.payments:
            if p.customer_id not in self.cust_payments:
                self.cust_payments[p.customer_id] = []
            self.cust_payments[p.customer_id].append(p)

        # Sort each customer's payments by created_at for O(log N) point-in-time safety
        for cid in self.cust_payments:
            self.cust_payments[cid].sort(key=lambda p: p.created_at)

        # Group cases by customer
        self.cust_cases: dict[Any, list[RecoveryCase]] = {}
        for c in self.cases:
            if c.customer_id not in self.cust_cases:
                self.cust_cases[c.customer_id] = []
            self.cust_cases[c.customer_id].append(c)

        for cid in self.cust_cases:
            self.cust_cases[cid].sort(key=lambda c_item: c_item.created_at)

        # Group payments by gateway for fast O(log N) historical lookup
        self.gw_payments: dict[str, list[Payment]] = {}
        self.gw_timestamps: dict[str, list[Any]] = {}
        self.gw_failed_cum: dict[str, list[int]] = {}

        for p in sorted(self.payments, key=lambda x: x.created_at):
            gw_key = p.gateway or "UNKNOWN"
            if gw_key not in self.gw_payments:
                self.gw_payments[gw_key] = []
                self.gw_timestamps[gw_key] = []
                self.gw_failed_cum[gw_key] = []

            self.gw_payments[gw_key].append(p)
            self.gw_timestamps[gw_key].append(p.created_at)

            prev_cum = self.gw_failed_cum[gw_key][-1] if self.gw_failed_cum[gw_key] else 0
            self.gw_failed_cum[gw_key].append(prev_cum + (1 if p.status == "failed" else 0))

    def extract_features(self, case: RecoveryCase) -> dict[str, Any]:
        """
        Extract features available at the diagnosis prediction timestamp.

        NOTE: Explicit provider failure codes (failure_code) are handled exclusively by
        the DeterministicRootCauseMapper and are excluded here to ensure the ML fallback
        learns purely from contextual customer, timing, and transaction covariates.
        """
        customer = self.customers_map[case.customer_id]

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

        # Historical records strictly before case creation using bisect (O(log N))
        all_cust_pay = self.cust_payments.get(case.customer_id, [])
        pay_times = [p.created_at for p in all_cust_pay]
        idx_p = bisect.bisect_left(pay_times, case.created_at)
        past_payments = all_cust_pay[:idx_p]

        all_cust_c = self.cust_cases.get(case.customer_id, [])
        case_times = [c.created_at for c in all_cust_c]
        idx_c = bisect.bisect_left(case_times, case.created_at)
        past_cases = all_cust_c[:idx_c]

        features: dict[str, Any] = {}

        # 1. Source & Transaction Features
        amount = float(case.amount_at_risk)
        ltv = max(1.0, float(customer.lifetime_value or 1.0))
        hour = case.created_at.hour
        weekday = case.created_at.weekday()

        features["source_type"] = case.source_type
        features["amount"] = amount
        features["log_amount"] = math.log1p(max(0.0, amount))
        features["amount_to_ltv_ratio"] = amount / ltv
        features["hour"] = hour
        features["weekday"] = weekday
        features["day_of_month"] = case.created_at.day
        features["is_weekend"] = 1 if weekday >= 5 else 0
        features["is_end_of_month"] = 1 if case.created_at.day > 22 else 0
        features["is_start_of_month"] = 1 if case.created_at.day <= 5 else 0
        features["is_peak_shopping_hours"] = 1 if 18 <= hour <= 22 else 0
        features["is_off_peak_hours"] = 1 if hour < 7 or hour >= 22 else 0

        # Cyclic Time Encodings
        features["hour_sin"] = math.sin(2 * math.pi * hour / 24.0)
        features["hour_cos"] = math.cos(2 * math.pi * hour / 24.0)
        features["weekday_sin"] = math.sin(2 * math.pi * weekday / 7.0)
        features["weekday_cos"] = math.cos(2 * math.pi * weekday / 7.0)

        if trigger_payment:
            features["payment_method"] = trigger_payment.payment_method
            features["gateway"] = trigger_payment.gateway or "UNKNOWN"
        else:
            features["payment_method"] = "invoice"
            features["gateway"] = "direct_bank"

        # 2. Customer Profile Features
        features["customer_age_days"] = max(
            0, (case.created_at.date() - customer.customer_since.date()).days
        )
        features["active_subscriptions"] = customer.active_subscriptions
        features["lifetime_value"] = ltv
        features["payment_reliability_score"] = float(customer.payment_reliability_score or 0.0)
        features["avg_payment_delay_days"] = float(customer.avg_payment_delay_days or 0.0)

        # 3. Dynamic Historical & Timing Features (Strictly events < case.created_at)
        past_failures = [p for p in past_payments if p.status == "failed"]
        past_successes = [p for p in past_payments if p.status == "successful"]

        if past_payments:
            features["historical_success_rate"] = len(past_successes) / len(past_payments)
            features["failure_count"] = len(past_failures)
        else:
            features["historical_success_rate"] = 1.0
            features["failure_count"] = 0

        # Rolling 7d & 30d Window Features
        cutoff_7d = case.created_at - pd.Timedelta(days=7)
        cutoff_30d = case.created_at - pd.Timedelta(days=30)

        recent_7d = [p for p in past_payments if p.created_at >= cutoff_7d]
        recent_30d = [p for p in past_payments if p.created_at >= cutoff_30d]

        features["failures_last_7d"] = sum(1 for p in recent_7d if p.status == "failed")
        features["failures_last_30d"] = sum(1 for p in recent_30d if p.status == "failed")
        features["successes_last_7d"] = sum(1 for p in recent_7d if p.status == "successful")
        features["successes_last_30d"] = sum(1 for p in recent_30d if p.status == "successful")

        past_closed = [
            c
            for c in past_cases
            if c.status in ("RECOVERED", "CLOSED") and c.updated_at < case.created_at
        ]
        if past_closed:
            recovered_count = sum(1 for c in past_closed if c.status == "RECOVERED")
            features["prior_recovery_rate"] = recovered_count / len(past_closed)
        else:
            features["prior_recovery_rate"] = 0.5

        # 4. Consecutive Failures & Time Since Last Events
        if past_failures:
            last_fail = max(past_failures, key=lambda p: p.created_at)
            time_since_fail = (case.created_at - last_fail.created_at).total_seconds() / 86400.0
            features["time_since_last_failure_days"] = time_since_fail
            features["rapid_retry_indicator"] = 1 if time_since_fail < 1.0 else 0
        else:
            features["time_since_last_failure_days"] = 999.0
            features["rapid_retry_indicator"] = 0

        if past_successes:
            last_succ = max(past_successes, key=lambda p: p.created_at)
            time_since_succ = (case.created_at - last_succ.created_at).total_seconds() / 86400.0
            features["time_since_last_success_days"] = time_since_succ
        else:
            features["time_since_last_success_days"] = 999.0

        # Calculate consecutive failure count at end of past_payments
        consec_fails = 0
        for p in reversed(past_payments):
            if p.status == "failed":
                consec_fails += 1
            else:
                break
        features["consecutive_failure_count"] = consec_fails
        features["rapid_retry_x_consec"] = features["rapid_retry_indicator"] * consec_fails
        features["rapid_retry_div_time"] = features["rapid_retry_indicator"] / max(
            features["time_since_last_failure_days"], 0.1
        )

        consec_succs = 0
        for p in reversed(past_payments):
            if p.status == "successful":
                consec_succs += 1
            else:
                break
        features["consecutive_success_count"] = consec_succs

        # 5. Gateway Historical Failure Rate via O(log N) bisect lookup
        gw = features.get("gateway", "UNKNOWN")
        gw_ts = self.gw_timestamps.get(gw, [])
        if gw_ts:
            idx_gw = bisect.bisect_left(gw_ts, case.created_at)
            if idx_gw > 0:
                fails_gw = self.gw_failed_cum[gw][idx_gw - 1]
                features["gateway_historical_failure_rate"] = fails_gw / idx_gw
            else:
                features["gateway_historical_failure_rate"] = 0.05
        else:
            features["gateway_historical_failure_rate"] = 0.05

        # 6. Telemetry & Causal Features
        features["card_expiry_remaining_days"] = (
            float(trigger_payment.card_expiry_remaining_days)
            if trigger_payment and trigger_payment.card_expiry_remaining_days is not None
            else 999.0
        )
        features["gateway_latency_ms"] = (
            float(trigger_payment.gateway_latency_ms)
            if trigger_payment and trigger_payment.gateway_latency_ms is not None
            else 300.0
        )
        features["checkout_session_duration_s"] = (
            float(trigger_payment.checkout_session_duration_s)
            if trigger_payment and trigger_payment.checkout_session_duration_s is not None
            else 30.0
        )
        features["is_international"] = (
            1.0 if trigger_payment and trigger_payment.is_international else 0.0
        )

        # Interactions
        features["latency_x_offpeak"] = (
            features["gateway_latency_ms"] * features["is_off_peak_hours"]
        )
        features["expired_card_indicator"] = (
            1.0 if features["card_expiry_remaining_days"] <= 0 else 0.0
        )

        # Cross features
        features["gw_b_x_offpeak"] = (
            1.0
            if (features.get("gateway") == "gateway_b" and features.get("is_off_peak_hours"))
            else 0.0
        )
        features["gw_rate_x_offpeak"] = features.get(
            "gateway_historical_failure_rate", 0
        ) * features.get("is_off_peak_hours", 0)
        features["invoice_x_delay"] = (
            1.0
            if (
                features.get("payment_method") == "invoice"
                and features.get("avg_payment_delay_days", 0) > 0
            )
            else 0.0
        )
        features["invoice_x_endmonth"] = (
            1.0
            if (features.get("payment_method") == "invoice" and features.get("is_end_of_month"))
            else 0.0
        )
        features["card_x_age"] = (
            1.0
            if (
                features.get("payment_method") == "card"
                and features.get("customer_age_days", 0) > 30
            )
            else 0.0
        )
        features["upi_nb_x_evening"] = (
            1.0
            if (
                features.get("payment_method") in ["upi", "netbanking"]
                and features.get("is_off_peak_hours")
            )
            else 0.0
        )
        features["rel_x_amt_ltv"] = features.get("payment_reliability_score", 0) * features.get(
            "amount_to_ltv_ratio", 0
        )
        features["rel_x_endmonth"] = features.get("payment_reliability_score", 0) * features.get(
            "is_end_of_month", 0
        )
        features["card_upi_x_startmonth"] = (
            1.0
            if (
                features.get("payment_method") in ["card", "upi"]
                and features.get("is_start_of_month")
            )
            else 0.0
        )

        return features

    def extract_all(self, target_cases: list[RecoveryCase]) -> pd.DataFrame:
        """Extract features and target label for a batch of cases."""
        rows = []
        for case in target_cases:
            feat = self.extract_features(case)
            feat["label"] = case.root_cause or "UNKNOWN"
            feat["case_id"] = str(case.case_id)
            feat["created_at"] = case.created_at
            rows.append(feat)

        return pd.DataFrame(rows)
