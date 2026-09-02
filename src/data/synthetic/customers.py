"""Synthetic generator for customers."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from src.data.synthetic.base import BaseGenerator
from src.data.synthetic.config import GenerationConfig
from src.database.models import Customer


class CustomerGenerator(BaseGenerator):
    """Generates synthetic customer records based on archetypes."""

    def __init__(self, config: GenerationConfig) -> None:
        super().__init__(seed=config.seed)
        self.config = config
        self.archetype_names = list(self.config.archetypes.keys())
        self.archetype_weights = [arch["weight"] for arch in self.config.archetypes.values()]
        self.start_date = datetime.fromisoformat(self.config.start_date.replace("Z", "+00:00"))

    def generate(self) -> list[Customer]:
        """Generate the configured number of customers."""
        customers = []

        # We want to distribute customer_since dates across the last 5 years
        # to ensure realistic tenure.
        max_days_past = 365 * 5

        for _ in range(self.config.num_customers):
            # Select archetype
            archetype_name = self.select_weighted(self.archetype_names, self.archetype_weights)
            arch = self.config.archetypes[archetype_name]

            # Generate latent behavioral attributes (these are not saved in the DB but
            # would be used in a real simulation to drive actions. Since we only
            # save the DB model, we might just store archetype info implicitly or
            # use the reliability score directly.)

            # payment_reliability_score: Beta distribution
            reliability = self.py_rng.betavariate(
                arch["base_reliability_alpha"], arch["base_reliability_beta"]
            )
            # Ensure bounds
            reliability = max(0.0, min(1.0, reliability))

            # avg_payment_delay_days: Normal distribution truncated at 0
            delay = self.py_rng.normalvariate(arch["base_delay_mu"], arch["base_delay_sigma"])
            delay = max(0.0, delay)

            # lifetime_value: Log-normal distribution
            ltv = self.py_rng.lognormvariate(
                arch["lifetime_value_mu"], arch["lifetime_value_sigma"]
            )
            # Assign preferred channel based on archetype weights
            channels = [c[0] for c in arch["preferred_channels"]]
            c_weights = [c[1] for c in arch["preferred_channels"]]
            preferred_channel = self.select_weighted(channels, c_weights)

            # Assign country and city (mock)
            country = "IN"  # Default as per currency INR
            cities = ["Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai", "Pune"]
            city = self.py_rng.choice(cities)

            # language
            language = self.py_rng.choice(["en", "hi", "hinglish"])

            # customer since
            days_ago = self.py_rng.randint(0, max_days_past)
            # A little timedelta math without importing timedelta
            # We can just use it if we import it, let's import it above, wait, I'll just use simple logic or import timedelta inside.
            from datetime import timedelta

            customer_since = self.start_date - timedelta(days=days_ago)

            # Communication opt-out (small global chance, maybe higher for high risk)
            opt_out = self.py_rng.random() < 0.05

            customer = Customer(
                customer_id=uuid.UUID(int=self.py_rng.getrandbits(128)),
                customer_type=arch["customer_type"],
                country=country,
                city=city,
                language=language,
                preferred_channel=preferred_channel,
                customer_since=customer_since,
                payment_reliability_score=Decimal(f"{reliability:.5f}"),
                avg_payment_delay_days=Decimal(f"{delay:.4f}"),
                lifetime_value=Decimal(f"{ltv:.2f}"),
                active_subscriptions=0,  # Will be updated by SubscriptionGenerator
                communication_opt_out=opt_out,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

            # Store the archetype dynamically for downstream generators to use
            customer._archetype = archetype_name  # type: ignore

            customers.append(customer)

        return customers
