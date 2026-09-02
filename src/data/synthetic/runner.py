"""Runner for generating and validating the synthetic environment."""

from typing import Any

from src.data.synthetic.cases import RecoveryGenerator
from src.data.synthetic.checks import DataQualityChecker
from src.data.synthetic.config import GenerationConfig
from src.data.synthetic.customers import CustomerGenerator
from src.data.synthetic.payments import PaymentGenerator
from src.data.synthetic.subscriptions import SubscriptionGenerator


class SyntheticEnvironment:
    """Orchestrates the creation and validation of synthetic data."""

    def __init__(self, config: GenerationConfig | None = None) -> None:
        self.config = config or GenerationConfig()
        self.customer_gen = CustomerGenerator(self.config)
        self.subscription_gen = SubscriptionGenerator(self.config)
        self.payment_gen = PaymentGenerator(self.config)
        self.recovery_gen = RecoveryGenerator(self.config)
        self.checker = DataQualityChecker()

    def generate(self) -> dict[str, Any]:
        """Run the full generation pipeline and return all entity lists."""
        # 1. Customers
        customers = self.customer_gen.generate()

        # 2. Subscriptions & Invoices
        subscriptions, invoices = self.subscription_gen.generate(customers)

        # 3. Payments
        payments = self.payment_gen.generate(customers, subscriptions)

        # 4. Recovery Cases, Interactions, Interventions, Outcomes
        cases, interactions, interventions, outcomes = self.recovery_gen.generate(
            customers, payments, invoices
        )

        # 5. Data Quality Checks
        self.checker.check(
            customers,
            subscriptions,
            payments,
            invoices,
            cases,
            interactions,
            interventions,
            outcomes,
        )

        return {
            "customers": customers,
            "subscriptions": subscriptions,
            "payments": payments,
            "invoices": invoices,
            "recovery_cases": cases,
            "interactions": interactions,
            "interventions": interventions,
            "outcomes": outcomes,
        }
