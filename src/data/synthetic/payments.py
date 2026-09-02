"""Synthetic generator for payments and payment failures."""

import math
import uuid
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from src.data.synthetic.base import BaseGenerator
from src.data.synthetic.config import GenerationConfig
from src.database.models import Customer, Payment, Subscription


class PaymentGenerator(BaseGenerator):
    """Generates synthetic payments based on subscriptions and failure mechanics."""

    PROVIDER_CODE_MAP: ClassVar[dict[str, str]] = {
        "EXPIRED_CARD": "ERR_EXPIRED_101",
        "INSUFFICIENT_FUNDS": "ERR_NSF_201",
        "INVALID_PAYMENT_METHOD": "ERR_INV_METHOD_301",
        "GATEWAY_FAILURE": "ERR_GW_FAIL_401",
        "NETWORK_TIMEOUT": "ERR_NET_TIMEOUT_501",
        "TEMPORARY_ISSUER_DECLINE": "ERR_DECLINE_601",
        "CUSTOMER_ABANDONMENT": "ERR_ABANDON_701",
        "DUPLICATE_PAYMENT": "ERR_DUP_801",
        "OVERDUE_INVOICE": "ERR_INV_OVERDUE_901",
        "UNKNOWN": "ERR_GENERIC_999",
    }

    def __init__(self, config: GenerationConfig) -> None:
        super().__init__(seed=config.seed)
        self.config = config

    def _determine_failure_reason(
        self,
        customer: Customer,
        payment_method: str,
        gateway_name: str,
        amount: float,
        occurred_at: datetime,
        past_failures: int,
        customer_age_days: int,
        time_since_last_failure_days: float | None,
        retry_count: int,
        card_expiry_remaining_days: int | None,
        gateway_latency_ms: int | None,
        checkout_session_duration_s: int | None,
        is_international: bool,
    ) -> str:
        """
        Select a failure reason using a soft additive logit mechanism.
        Prevalence is controlled via base logit offsets; learnability is controlled via conditional multipliers.
        Target: Max posterior purity ~45-55% with balanced fallback class prevalence.
        """
        reasons = [f["reason"] for f in self.config.failure_mechanisms]

        # Base Logit Offsets to control class prevalence independently of signal strength
        base_logits: dict[str, float] = {
            "TEMPORARY_ISSUER_DECLINE": 0.45,
            "INSUFFICIENT_FUNDS": -0.75,
            "EXPIRED_CARD": 0.15,
            "INVALID_PAYMENT_METHOD": 0.55,
            "GATEWAY_FAILURE": -0.10,
            "NETWORK_TIMEOUT": -0.10,
            "CUSTOMER_ABANDONMENT": -0.10,
            "DUPLICATE_PAYMENT": -0.20,
            "OVERDUE_INVOICE": 0.35,
            "UNKNOWN": 0.10,
        }
        logits = {r: base_logits.get(str(r), 0.0) for r in reasons}

        rel_score = float(customer.payment_reliability_score or 0.5)
        ltv = max(1.0, float(customer.lifetime_value or 1.0))
        amount_to_ltv_ratio = amount / ltv
        day_of_month = occurred_at.day
        avg_delay = float(customer.avg_payment_delay_days or 0.0)

        # 1. EXPIRED_CARD (Card + Account Tenure Cycle + High Reliability)
        if payment_method == "card":
            if card_expiry_remaining_days is not None and card_expiry_remaining_days <= 0:
                logits["EXPIRED_CARD"] += 4.5
            else:
                logits["EXPIRED_CARD"] -= 3.0

        # 2. INVALID_PAYMENT_METHOD (Card/Netbanking + New Account Tenure + High Delay + Early Failures)
        if payment_method in ("card", "netbanking"):
            is_intl_penalty = 3.5 if is_international else 0.0
            new_account_factor = max(0.0, 1.0 - (customer_age_days / 180.0))
            logits["INVALID_PAYMENT_METHOD"] += (
                is_intl_penalty + 1.5 * new_account_factor + 1.0 * (1.0 - rel_score)
            )

        # 3. CUSTOMER_ABANDONMENT (UPI/Netbanking + Peak Evening Hours + Payment Delay)
        if payment_method in ("upi", "netbanking"):
            session_penalty = (
                3.0
                if checkout_session_duration_s is not None and checkout_session_duration_s > 600
                else 0.0
            )
            logits["CUSTOMER_ABANDONMENT"] += (
                session_penalty + 1.0 * min(1.0, avg_delay / 4.0) + 0.8 * (1.0 - rel_score)
            )

        # 4. NETWORK_TIMEOUT (UPI/Netbanking + Off-Peak/Night/Weekend Hours + Gateway B/C)
        if payment_method in ("upi", "netbanking"):
            timeout_penalty = (
                3.5 if gateway_latency_ms is not None and gateway_latency_ms > 4500 else 0.0
            )
            gw_factor = 1.0 if gateway_name in ("gateway_b", "gateway_c") else 0.3
            logits["NETWORK_TIMEOUT"] += (
                timeout_penalty + 1.0 * gw_factor + 0.5 * min(1.0, past_failures / 3.0)
            )

        # 5. INSUFFICIENT_FUNDS (Low Reliability + Amount/LTV Ratio + End of Month)
        low_rel_factor = max(0.0, (0.55 - rel_score) / 0.55)
        high_amount_factor = min(1.5, amount_to_ltv_ratio / 0.04)
        end_of_month_factor = 1.0 if day_of_month > 20 else 0.0

        logits["INSUFFICIENT_FUNDS"] += (
            1.8 * low_rel_factor
            + 1.4 * high_amount_factor
            + 1.4 * end_of_month_factor
            + 0.6 * min(1.0, past_failures / 3.0)
        )

        # 6. TEMPORARY_ISSUER_DECLINE (High Reliability + Start/Mid Month + Card/UPI Payment)
        if payment_method in ("card", "upi"):
            start_mid_month_factor = 1.0 if day_of_month <= 15 else 0.0
            high_rel_factor = max(0.0, (rel_score - 0.45) / 0.55)
            logits["TEMPORARY_ISSUER_DECLINE"] += (
                2.0 * start_mid_month_factor
                + 1.4 * high_rel_factor
                + 0.6 * (1.0 - min(1.0, amount_to_ltv_ratio))
            )

        # 7. GATEWAY_FAILURE (Gateway B/C Degradation + High Failure History + Night/Weekend)
        if gateway_name in ("gateway_b", "gateway_c"):
            gw_latency_penalty = (
                2.5
                if gateway_latency_ms is not None and 2000 <= gateway_latency_ms <= 4500
                else 0.0
            )
            gw_b_factor = 1.5 if gateway_name == "gateway_b" else 0.8
            logits["GATEWAY_FAILURE"] += (
                gw_latency_penalty + gw_b_factor + 0.6 * min(1.0, past_failures / 3.0)
            )

        # 8. DUPLICATE_PAYMENT (Rapid Retry Interval + Retry Count >= 1)
        if time_since_last_failure_days is not None and time_since_last_failure_days < 1.5:
            rapid_retry_factor = max(0.0, 1.0 - (time_since_last_failure_days / 1.5))
            retry_count_factor = min(1.5, float(retry_count + 1))
            logits["DUPLICATE_PAYMENT"] += 2.6 * rapid_retry_factor + 1.2 * retry_count_factor

        # 9. OVERDUE_INVOICE (Invoice Payment Method / B2B Context + High Payment Delay)
        if payment_method == "invoice":
            logits["OVERDUE_INVOICE"] += 2.8 + 1.2 * min(2.0, avg_delay / 3.0)
        else:
            if avg_delay > 3.0 and day_of_month > 15:
                logits["OVERDUE_INVOICE"] += 1.2 + 0.6 * min(2.0, avg_delay / 4.0)

        # 10. UNKNOWN (Residual ambient noise: base logit 0.10 with minor random perturbation)
        logits["UNKNOWN"] += 0.3 * (rel_score - 0.5)

        # Convert logits to soft probabilities via numerically stable Softmax with temperature T=1.0
        max_logit = max(logits.values())
        exp_logits = [math.exp(logits[r] - max_logit) for r in reasons]
        sum_exp = sum(exp_logits)
        probs = [e / sum_exp for e in exp_logits]

        return str(self.select_weighted(reasons, probs))

    def _determine_failure_code(self, failure_reason: str) -> str:
        """Map failure reason to a provider failure code, including generic/ambiguous codes."""
        # 35% of failures emit a generic provider code (ERR_GENERIC_9xx), which falls through to ML
        if self.py_rng.random() < 0.35:
            return f"ERR_GENERIC_{self.py_rng.randint(900, 999)}"

        return self.PROVIDER_CODE_MAP.get(
            failure_reason, f"ERR_GENERIC_{self.py_rng.randint(900, 999)}"
        )

    def generate(
        self, customers: list[Customer], subscriptions: list[Subscription]
    ) -> list[Payment]:
        """Generate payments for the given subscriptions."""
        payments = []

        cust_map = {c.customer_id: c for c in customers}
        cust_failures: dict[uuid.UUID, int] = {c.customer_id: 0 for c in customers}
        last_failure_time: dict[uuid.UUID, datetime | None] = {
            c.customer_id: None for c in customers
        }

        gateways = [g["name"] for g in self.config.gateways]
        gateway_weights = [g["weight"] for g in self.config.gateways]

        months_to_simulate = self.config.num_months

        sim_start_date = datetime.fromisoformat(
            self.config.start_date.replace("Z", "+00:00")
        ).date()
        sim_end_date = sim_start_date + timedelta(days=self.config.num_months * 30)

        for sub in subscriptions:
            customer = cust_map[sub.customer_id]
            current_date = sub.start_date

            for m in range(months_to_simulate):
                if current_date > sim_end_date:
                    break

                gateway = self.select_weighted(gateways, gateway_weights)
                g_config = next(g for g in self.config.gateways if g["name"] == gateway)

                rel_score = float(customer.payment_reliability_score or 0.0)
                base_s = float(g_config["base_success"])  # type: ignore
                success_prob = rel_score * base_s

                is_weekend = current_date.weekday() >= 5
                if is_weekend:
                    success_prob *= 0.95

                # Expand hour generation to cover the full 24-hour cycle (randint 0 to 23)
                occurred_at = datetime.combine(
                    current_date, datetime.min.time(), tzinfo=UTC
                ) + timedelta(hours=self.py_rng.randint(0, 23), minutes=self.py_rng.randint(0, 59))

                customer_age_days = max(
                    0, (occurred_at.date() - customer.customer_since.date()).days
                )

                prev_fail_at = last_failure_time[customer.customer_id]
                time_since_last_failure_days = None
                if prev_fail_at is not None:
                    time_since_last_failure_days = (
                        occurred_at - prev_fail_at
                    ).total_seconds() / 86400.0

                status = "successful"
                failure_reason = None
                failure_code = None

                # Allow B2B business customers to use invoice payment method
                if customer.customer_type == "business" and self.py_rng.random() < 0.35:
                    payment_method = "invoice"
                else:
                    payment_method = self.py_rng.choice(["card", "upi", "netbanking"])

                amount = float(str(sub.amount))

                is_success = self.py_rng.random() < success_prob
                # Inject observable telemetry
                card_expiry_remaining_days = None
                if payment_method == "card":
                    days_in_year_cycle = customer_age_days % 365
                    if days_in_year_cycle >= 350:
                        card_expiry_remaining_days = (
                            365 - days_in_year_cycle - 20
                        )  # Negative/0 for expired
                    else:
                        card_expiry_remaining_days = 365 - days_in_year_cycle

                gateway_latency_ms = self.py_rng.randint(200, 800)
                if not is_success:
                    rand_gw = self.py_rng.random()
                    if rand_gw < 0.15:
                        gateway_latency_ms = self.py_rng.randint(4501, 8000)
                    elif rand_gw < 0.35:
                        gateway_latency_ms = self.py_rng.randint(2000, 4500)

                checkout_session_duration_s = self.py_rng.randint(15, 120)
                if not is_success and self.py_rng.random() < 0.15:
                    checkout_session_duration_s = self.py_rng.randint(601, 1500)

                is_international = self.py_rng.random() < 0.05

                if not is_success:
                    status = "failed"
                    past_f = cust_failures[customer.customer_id]
                    failure_reason = self._determine_failure_reason(
                        customer=customer,
                        payment_method=payment_method,
                        gateway_name=gateway,
                        amount=amount,
                        occurred_at=occurred_at,
                        past_failures=past_f,
                        customer_age_days=customer_age_days,
                        time_since_last_failure_days=time_since_last_failure_days,
                        retry_count=0,
                        card_expiry_remaining_days=card_expiry_remaining_days,
                        gateway_latency_ms=gateway_latency_ms,
                        checkout_session_duration_s=checkout_session_duration_s,
                        is_international=is_international,
                    )
                    failure_code = self._determine_failure_code(failure_reason)
                    cust_failures[customer.customer_id] += 1
                    last_failure_time[customer.customer_id] = occurred_at

                payment = Payment(
                    payment_id=uuid.UUID(int=self.py_rng.getrandbits(128)),
                    customer_id=customer.customer_id,
                    subscription_id=sub.subscription_id,
                    amount=sub.amount,
                    currency=sub.currency,
                    occurred_at=occurred_at,
                    payment_method=payment_method,
                    gateway=gateway,
                    status=status,
                    failure_code=failure_code,
                    failure_reason=failure_reason,
                    retry_count=0,
                    idempotency_key=f"idem_pay_{sub.subscription_id}_{m}",
                    provider_reference=f"prov_{uuid.uuid4().hex[:8]}",
                    created_at=occurred_at,
                    updated_at=occurred_at,
                    card_expiry_remaining_days=card_expiry_remaining_days,
                    gateway_latency_ms=gateway_latency_ms,
                    checkout_session_duration_s=checkout_session_duration_s,
                    is_international=is_international,
                )
                payments.append(payment)

                # Simulate rapid retry payments when a payment fails (25% chance of customer rapid retry within 2-6 hours)
                if not is_success and self.py_rng.random() < 0.25:
                    retry_time = occurred_at + timedelta(hours=self.py_rng.randint(2, 6))
                    if retry_time.date() <= sim_end_date:
                        retry_time_since = (retry_time - occurred_at).total_seconds() / 86400.0
                        retry_reason = self._determine_failure_reason(
                            customer=customer,
                            payment_method=payment_method,
                            gateway_name=gateway,
                            amount=amount,
                            occurred_at=retry_time,
                            past_failures=cust_failures[customer.customer_id],
                            customer_age_days=customer_age_days,
                            time_since_last_failure_days=retry_time_since,
                            retry_count=1,
                            card_expiry_remaining_days=card_expiry_remaining_days,
                            gateway_latency_ms=gateway_latency_ms,
                            checkout_session_duration_s=checkout_session_duration_s,
                            is_international=is_international,
                        )
                        retry_code = self._determine_failure_code(retry_reason)
                        cust_failures[customer.customer_id] += 1
                        last_failure_time[customer.customer_id] = retry_time

                        retry_payment = Payment(
                            payment_id=uuid.UUID(int=self.py_rng.getrandbits(128)),
                            customer_id=customer.customer_id,
                            subscription_id=sub.subscription_id,
                            amount=sub.amount,
                            currency=sub.currency,
                            occurred_at=retry_time,
                            payment_method=payment_method,
                            gateway=gateway,
                            status="failed",
                            failure_code=retry_code,
                            failure_reason=retry_reason,
                            retry_count=1,
                            idempotency_key=f"idem_retry_{sub.subscription_id}_{m}",
                            provider_reference=f"prov_retry_{uuid.uuid4().hex[:8]}",
                            created_at=retry_time,
                            updated_at=retry_time,
                            card_expiry_remaining_days=card_expiry_remaining_days,
                            gateway_latency_ms=gateway_latency_ms,
                            checkout_session_duration_s=checkout_session_duration_s,
                            is_international=is_international,
                        )
                        payments.append(retry_payment)

                current_date = current_date + timedelta(days=30)

        return payments
