"""Feature extraction for the Recovery Propensity model."""

from typing import Any

import pandas as pd

from src.database.models import Customer, Payment, RecoveryCase


class RecoveryPropensityFeatureExtractor:
    """Extracts features for predicting recovery probability."""

    def __init__(self) -> None:
        pass

    def extract(
        self,
        case: RecoveryCase,
        customer: Customer,
        action_type: str,
        attempt_number: int,
        trigger_payment: Payment | None = None,
    ) -> dict[str, Any]:
        """Extract features observable before the intervention.

        Args:
            case: The recovery case
            customer: The customer object
            action_type: The candidate action to take (e.g. "RETRY_LATER", "EMAIL_REMINDER")
            attempt_number: The attempt number of this intervention (1, 2, 3...)
            trigger_payment: The payment that caused this case

        Returns:
            Dictionary of features
        """
        features: dict[str, Any] = {}

        # 1. Action-Aware Features (CRITICAL for Milestone 6)
        features["action_type"] = action_type
        features["attempt_number"] = float(attempt_number)
        features["attempt_number_sq"] = float(attempt_number**2)

        cost_map = {"EMAIL_REMINDER": 0.05, "SMS_REMINDER": 0.10, "RETRY_LATER": 0.10}
        features["action_cost"] = cost_map.get(action_type, 0.10)

        # 2. Case Features
        features["amount_at_risk"] = float(case.amount_at_risk)
        features["risk_score"] = float(case.risk_score) if case.risk_score is not None else 0.5

        # Use predicted root cause if available, fallback to actual
        features["root_cause"] = case.root_cause if case.root_cause else "UNKNOWN"
        features["root_cause_confidence"] = (
            float(case.root_cause_confidence) if case.root_cause_confidence is not None else 1.0
        )

        # Time since failure
        time_since_failure_h = 24.0  # Default fallback
        if trigger_payment and case.created_at:
            time_since_failure_h = (
                case.created_at - trigger_payment.occurred_at
            ).total_seconds() / 3600.0
        features["time_since_failure_hours"] = time_since_failure_h

        # 3. Customer Features
        features["payment_reliability_score"] = (
            float(customer.payment_reliability_score)
            if customer.payment_reliability_score is not None
            else 0.5
        )
        features["lifetime_value"] = float(customer.lifetime_value)
        features["active_subscriptions"] = float(customer.active_subscriptions)
        features["avg_payment_delay_days"] = (
            float(customer.avg_payment_delay_days)
            if customer.avg_payment_delay_days is not None
            else 0.0
        )

        # Economic Ratios
        features["amount_to_ltv_ratio"] = float(case.amount_at_risk) / max(
            1.0, float(customer.lifetime_value)
        )
        features["amount_to_subs_ratio"] = float(case.amount_at_risk) / max(
            1.0, float(customer.active_subscriptions)
        )

        if customer.customer_since and case.created_at:
            customer_age_days = (case.created_at.date() - customer.customer_since.date()).days
        else:
            customer_age_days = 30
        features["customer_age_days"] = float(customer_age_days)

        # 4. Telemetry
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

        # 5. Interactions
        # We model interactions between root cause and action type, because decision trees
        # can discover them but making them explicit helps linear baselines.

        is_retry = 1.0 if action_type == "RETRY_LATER" else 0.0
        is_comm = 1.0 if action_type in ("EMAIL_REMINDER", "SMS_REMINDER") else 0.0

        # Retry is good for transient issues
        is_transient = (
            1.0
            if features["root_cause"]
            in ("NETWORK_TIMEOUT", "GATEWAY_FAILURE", "TEMPORARY_ISSUER_DECLINE")
            else 0.0
        )
        features["retry_transient_interaction"] = is_retry * is_transient

        # Comm is good for customer-driven issues
        is_cust_issue = (
            1.0
            if features["root_cause"]
            in ("EXPIRED_CARD", "INSUFFICIENT_FUNDS", "INVALID_PAYMENT_METHOD")
            else 0.0
        )
        features["comm_cust_issue_interaction"] = is_comm * is_cust_issue

        # Hard block: retrying expired card
        features["retry_expired_card_interaction"] = is_retry * (
            1.0 if features["root_cause"] == "EXPIRED_CARD" else 0.0
        )

        return features

    def extract_all(self, data: list[dict[str, Any]]) -> pd.DataFrame:
        """Extract features for a list of dictionaries.

        Expects keys: case, customer, action_type, attempt_number, trigger_payment.
        """
        records = []
        for d in data:
            records.append(
                self.extract(
                    case=d["case"],
                    customer=d["customer"],
                    action_type=d["action_type"],
                    attempt_number=d["attempt_number"],
                    trigger_payment=d.get("trigger_payment"),
                )
            )

        return pd.DataFrame(records)
