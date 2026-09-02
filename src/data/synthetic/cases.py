"""Synthetic generator for recovery cases, interactions, interventions, and outcomes."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from src.data.synthetic.base import BaseGenerator
from src.data.synthetic.config import GenerationConfig
from src.database.models import (
    Customer,
    Interaction,
    Intervention,
    Invoice,
    Outcome,
    Payment,
    RecoveryCase,
)


class RecoveryGenerator(BaseGenerator):
    """Generates synthetic recovery cases and the full intervention lifecycle."""

    def __init__(self, config: GenerationConfig) -> None:
        super().__init__(seed=config.seed)
        self.config = config

    def generate(
        self,
        customers: list[Customer],
        payments: list[Payment],
        invoices: list[Invoice],
    ) -> tuple[list[RecoveryCase], list[Interaction], list[Intervention], list[Outcome]]:
        """Generate recovery lifecycle records for failed payments and overdue invoices."""
        cases = []
        interactions = []
        interventions = []
        outcomes = []

        cust_map = {c.customer_id: c for c in customers}

        hinglish_examples = [
            "Kal shaam payment kar dunga.",
            "Aaj funds nahi hai, weekend pe karunga.",
            "Payment already kar diya hai.",
            "Please mujhe message mat karna.",
        ]

        # 1. Process Failed Payments
        failed_payments = [p for p in payments if p.status == "failed"]
        for payment in failed_payments:
            customer = cust_map[payment.customer_id]

            # Identify if failure is fundamentally recoverable
            f_mech = next(
                (
                    f
                    for f in self.config.failure_mechanisms
                    if f["reason"] == payment.failure_reason
                ),
                None,
            )
            f_mech["recoverable"] if f_mech else True

            rel_score = float(customer.payment_reliability_score or 0.0)
            risk_score = 1.0 - rel_score
            amount_at_risk = payment.amount or Decimal("0.00")

            case = RecoveryCase(
                case_id=uuid.UUID(int=self.py_rng.getrandbits(128)),
                customer_id=payment.customer_id,
                source_type="payment",
                source_id=payment.payment_id,
                amount_at_risk=amount_at_risk,
                risk_score=Decimal(f"{risk_score:.5f}"),
                root_cause=payment.failure_reason,
                root_cause_confidence=Decimal(f"{self.py_rng.uniform(0.7, 0.99):.5f}"),
                recovery_probability=Decimal("0.0"),  # Will be updated by propensity model later
                recommended_action="RETRY_LATER",
                expected_recovery=Decimal("0.0"),
                expected_net_recovery=Decimal("0.0"),
                decision_confidence=Decimal("0.0"),
                status="CLOSED",  # Updated below
                escalation_required=False,
                created_at=payment.occurred_at,
                updated_at=payment.occurred_at + timedelta(days=2),
                closed_at=payment.occurred_at + timedelta(days=2),
            )
            cases.append(case)

            # Generate Interventions & Outcomes
            num_interventions = self.py_rng.randint(1, 3)
            current_time = case.created_at

            for attempt in range(1, num_interventions + 1):
                current_time += timedelta(hours=self.py_rng.randint(2, 24))

                action_type = self.py_rng.choice(["EMAIL_REMINDER", "RETRY_LATER", "SMS_REMINDER"])
                cost = Decimal("0.05") if "EMAIL" in action_type else Decimal("0.10")

                # Causal Action Effectiveness Matrix
                base_prob = 0.01
                if payment.failure_reason in (
                    "NETWORK_TIMEOUT",
                    "GATEWAY_FAILURE",
                    "TEMPORARY_ISSUER_DECLINE",
                ):
                    base_prob = 0.7 + 0.2 * rel_score if action_type == "RETRY_LATER" else 0.05
                elif payment.failure_reason in ("EXPIRED_CARD", "INVALID_PAYMENT_METHOD"):
                    base_prob = 0.0 if action_type == "RETRY_LATER" else 0.15 + (0.35 * rel_score)
                elif payment.failure_reason == "INSUFFICIENT_FUNDS":
                    base_prob = (
                        0.10 + (0.20 * rel_score)
                        if action_type == "RETRY_LATER"
                        else 0.20 + (0.30 * rel_score)
                    )
                elif payment.failure_reason == "CUSTOMER_ABANDONMENT":
                    base_prob = 0.0 if action_type == "RETRY_LATER" else 0.1 + 0.2 * rel_score
                elif payment.failure_reason == "OVERDUE_INVOICE":
                    base_prob = 0.40 if "REMINDER" in action_type else 0.0

                # Diminishing returns on attempts
                base_prob *= 0.8 ** (attempt - 1)

                success = self.py_rng.random() < base_prob

                intervention = Intervention(
                    intervention_id=uuid.UUID(int=self.py_rng.getrandbits(128)),
                    case_id=case.case_id,
                    action_type=action_type,
                    attempt_number=attempt,
                    scheduled_at=current_time,
                    executed_at=current_time,
                    cost=cost,
                    policy_decision="ALLOW",
                    policy_version="1.0.0",
                    status="COMPLETED",
                    idempotency_key=f"idem_int_{case.case_id}_{attempt}",
                    created_at=current_time,
                )
                interventions.append(intervention)

                # Simulate a customer interaction if it's a communication
                if "REMINDER" in action_type:
                    msg = "Your payment failed. Please update your payment method."
                    cust_resp = None
                    if self.py_rng.random() < 0.2:
                        cust_resp = self.py_rng.choice(hinglish_examples)

                    interaction = Interaction(
                        interaction_id=uuid.UUID(int=self.py_rng.getrandbits(128)),
                        customer_id=customer.customer_id,
                        recovery_case_id=case.case_id,
                        channel=action_type.split("_")[0],
                        occurred_at=current_time + timedelta(minutes=self.py_rng.randint(10, 60)),
                        message=msg,
                        customer_response=cust_resp,
                        intent="PROMISE_TO_PAY" if cust_resp and "kar dunga" in cust_resp else None,
                        promise_to_pay=bool(cust_resp and "kar dunga" in cust_resp),
                        created_at=current_time,
                    )
                    interactions.append(interaction)

                # Outcome
                outcome = Outcome(
                    outcome_id=uuid.UUID(int=self.py_rng.getrandbits(128)),
                    case_id=case.case_id,
                    intervention_id=intervention.intervention_id,
                    success=success,
                    amount_recovered=amount_at_risk if success else Decimal("0.00"),
                    occurred_at=current_time + timedelta(minutes=5),
                    created_at=current_time + timedelta(minutes=5),
                )
                outcomes.append(outcome)

                if success:
                    case.status = "RECOVERED"
                    case.updated_at = current_time + timedelta(minutes=5)
                    case.closed_at = current_time + timedelta(minutes=5)
                    break  # Stop intervening if recovered

            # If we exhausted interventions without success, case stays CLOSED but wasn't recovered
            if not success:
                case.status = "CLOSED"
                case.updated_at = current_time + timedelta(days=1)
                case.closed_at = current_time + timedelta(days=1)

        # 2. Process Overdue Invoices
        overdue_invoices = [
            i
            for i in invoices
            if i.status == "overdue" or (i.status == "paid" and i.days_overdue > 0)
        ]
        for invoice in overdue_invoices:
            customer = cust_map[invoice.customer_id]
            case_status = "RECOVERED" if invoice.status == "paid" else "CLOSED"
            amount_at_risk = invoice.amount

            case = RecoveryCase(
                case_id=uuid.UUID(int=self.py_rng.getrandbits(128)),
                customer_id=invoice.customer_id,
                source_type="invoice",
                source_id=invoice.invoice_id,
                amount_at_risk=amount_at_risk,
                risk_score=Decimal("0.5"),
                root_cause="OVERDUE_INVOICE",
                root_cause_confidence=Decimal("0.95"),
                status=case_status,
                escalation_required=bool(amount_at_risk > 50000),
                created_at=datetime.combine(
                    invoice.due_date + timedelta(days=1), datetime.min.time(), tzinfo=UTC
                ),
                updated_at=invoice.paid_at or datetime.now(UTC),
                closed_at=invoice.paid_at or datetime.now(UTC),
            )
            cases.append(case)

            # Minimal interventions for invoices to save space, but similar logic applies
            attempt = 1
            current_time = case.created_at + timedelta(days=2)
            success = case_status == "RECOVERED"

            intervention = Intervention(
                intervention_id=uuid.UUID(int=self.py_rng.getrandbits(128)),
                case_id=case.case_id,
                action_type="EMAIL_REMINDER",
                attempt_number=attempt,
                scheduled_at=current_time,
                executed_at=current_time,
                cost=Decimal("0.10"),
                policy_decision="ALLOW",
                policy_version="1.0.0",
                status="COMPLETED",
                idempotency_key=f"idem_int_{case.case_id}_{attempt}",
                created_at=current_time,
            )
            interventions.append(intervention)

            outcome = Outcome(
                outcome_id=uuid.UUID(int=self.py_rng.getrandbits(128)),
                case_id=case.case_id,
                intervention_id=intervention.intervention_id,
                success=success,
                amount_recovered=amount_at_risk if success else Decimal("0.00"),
                occurred_at=current_time + timedelta(minutes=5),
                created_at=current_time + timedelta(minutes=5),
            )
            outcomes.append(outcome)

        return cases, interactions, interventions, outcomes
