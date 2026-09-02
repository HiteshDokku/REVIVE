"""Data quality checks for synthetic generation."""

from decimal import Decimal
from typing import Any

from src.database.models import (
    Customer,
    Interaction,
    Intervention,
    Invoice,
    Outcome,
    Payment,
    RecoveryCase,
    Subscription,
)


class DataQualityChecker:
    """Validates the relational integrity and quality of generated data."""

    def check(
        self,
        customers: list[Customer],
        subscriptions: list[Subscription],
        payments: list[Payment],
        invoices: list[Invoice],
        cases: list[RecoveryCase],
        interactions: list[Interaction],
        interventions: list[Intervention],
        outcomes: list[Outcome],
    ) -> bool:
        """Run all quality checks on the datasets."""
        self._check_duplicate_pks(
            customers,
            subscriptions,
            payments,
            invoices,
            cases,
            interactions,
            interventions,
            outcomes,
        )
        self._check_foreign_keys(
            customers,
            subscriptions,
            payments,
            invoices,
            cases,
            interactions,
            interventions,
            outcomes,
        )
        self._check_monetary_values(
            subscriptions, payments, invoices, cases, interventions, outcomes
        )
        self._check_logical_dates(subscriptions, invoices, interventions, outcomes)
        self._check_outcome_integrity(cases, outcomes)
        return True

    def _check_duplicate_pks(self, *datasets: list[Any]) -> None:
        """Ensure no duplicate primary keys exist."""
        # This is a bit dynamic for all entities
        for ds in datasets:
            if not ds:
                continue
            pk_attr = ds[0].__mapper__.primary_key[0].name
            pks = [getattr(e, pk_attr) for e in ds]
            if len(pks) != len(set(pks)):
                raise ValueError(f"Duplicate primary keys found in dataset: {type(ds[0]).__name__}")

    def _check_foreign_keys(
        self,
        customers: list[Customer],
        subscriptions: list[Subscription],
        payments: list[Payment],
        invoices: list[Invoice],
        cases: list[RecoveryCase],
        interactions: list[Interaction],
        interventions: list[Intervention],
        outcomes: list[Outcome],
    ) -> None:
        """Check all critical foreign keys."""
        cust_ids = {c.customer_id for c in customers}
        sub_ids = {s.subscription_id for s in subscriptions}
        case_ids = {c.case_id for c in cases}
        int_ids = {i.intervention_id for i in interventions}

        for s in subscriptions:
            assert s.customer_id in cust_ids, (
                f"Subscription {s.subscription_id} has invalid customer_id"
            )
        for p in payments:
            assert p.customer_id in cust_ids, f"Payment {p.payment_id} has invalid customer_id"
            if p.subscription_id:
                assert p.subscription_id in sub_ids, (
                    f"Payment {p.payment_id} has invalid subscription_id"
                )
        for inv in invoices:
            assert inv.customer_id in cust_ids, f"Invoice {inv.invoice_id} has invalid customer_id"
        for c in cases:
            assert c.customer_id in cust_ids, f"Case {c.case_id} has invalid customer_id"
        for intrt in interactions:
            assert intrt.customer_id in cust_ids, (
                f"Interaction {intrt.interaction_id} has invalid customer_id"
            )
            if intrt.recovery_case_id:
                assert intrt.recovery_case_id in case_ids, (
                    f"Interaction {intrt.interaction_id} has invalid case_id"
                )
        for intv in interventions:
            assert intv.case_id in case_ids, (
                f"Intervention {intv.intervention_id} has invalid case_id"
            )
        for o in outcomes:
            assert o.case_id in case_ids, f"Outcome {o.outcome_id} has invalid case_id"
            assert o.intervention_id in int_ids, (
                f"Outcome {o.outcome_id} has invalid intervention_id"
            )

    def _check_monetary_values(
        self,
        subscriptions: list[Subscription],
        payments: list[Payment],
        invoices: list[Invoice],
        cases: list[RecoveryCase],
        interventions: list[Intervention],
        outcomes: list[Outcome],
    ) -> None:
        """Check all money values are >= 0."""
        zero = Decimal("0.00")
        for s in subscriptions:
            assert s.amount > zero
        for p in payments:
            assert p.amount > zero
        for i in invoices:
            assert i.amount > zero
        for c in cases:
            assert c.amount_at_risk >= zero
            if c.expected_recovery is not None:
                assert c.expected_recovery >= zero
        for intv in interventions:
            assert intv.cost >= zero
        for o in outcomes:
            assert o.amount_recovered >= zero

    def _check_logical_dates(
        self,
        subscriptions: list[Subscription],
        invoices: list[Invoice],
        interventions: list[Intervention],
        outcomes: list[Outcome],
    ) -> None:
        """Check temporal consistency."""
        for s in subscriptions:
            assert s.next_billing_date >= s.start_date
        for i in invoices:
            assert i.due_date >= i.issue_date
            if i.paid_at:
                assert i.paid_at.date() >= i.issue_date

    def _check_outcome_integrity(self, cases: list[RecoveryCase], outcomes: list[Outcome]) -> None:
        """Check that amount recovered does not exceed risk."""
        case_map = {c.case_id: c for c in cases}

        # Calculate sum of recovered amounts per case
        recovered_sums = {c.case_id: Decimal("0.00") for c in cases}
        for o in outcomes:
            recovered_sums[o.case_id] += o.amount_recovered

        for case_id, amt in recovered_sums.items():
            assert amt <= case_map[case_id].amount_at_risk + Decimal("0.01"), (
                f"Recovered amount {amt} exceeds risk {case_map[case_id].amount_at_risk} for case {case_id}"
            )
