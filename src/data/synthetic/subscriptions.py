"""Synthetic generator for subscriptions and invoices."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from src.data.synthetic.base import BaseGenerator
from src.data.synthetic.config import GenerationConfig
from src.database.models import Customer, Invoice, Subscription


class SubscriptionGenerator(BaseGenerator):
    """Generates synthetic subscriptions and invoices for customers."""

    def __init__(self, config: GenerationConfig) -> None:
        super().__init__(seed=config.seed)
        self.config = config

    def generate(self, customers: list[Customer]) -> tuple[list[Subscription], list[Invoice]]:
        """Generate subscriptions and invoices for the given customers."""
        subscriptions = []
        invoices = []
        sim_start_date = datetime.fromisoformat(
            self.config.start_date.replace("Z", "+00:00")
        ).date()
        sim_end_date = sim_start_date + timedelta(days=self.config.num_months * 30)

        consumer_bands = [b["name"] for b in self.config.consumer_subscription_bands]
        consumer_weights = [b["weight"] for b in self.config.consumer_subscription_bands]

        business_bands = [b["name"] for b in self.config.business_subscription_bands]
        business_weights = [b["weight"] for b in self.config.business_subscription_bands]

        for customer in customers:
            # 0-4 subscriptions per customer
            num_subs = self.py_rng.choices(
                [0, 1, 2, 3, 4], weights=[0.2, 0.5, 0.2, 0.08, 0.02], k=1
            )[0]
            customer.active_subscriptions = num_subs

            for _ in range(num_subs):
                is_business = customer.customer_type == "business"
                if is_business:
                    band_name = self.select_weighted(business_bands, business_weights)
                    band = next(
                        b for b in self.config.business_subscription_bands if b["name"] == band_name
                    )
                else:
                    band_name = self.select_weighted(consumer_bands, consumer_weights)
                    band = next(
                        b for b in self.config.consumer_subscription_bands if b["name"] == band_name
                    )

                # Skewed amount within the band
                # using a truncated log-normal or just exponential decay inside the range
                # Simple approximation: beta distribution shifted and scaled
                fraction = self.py_rng.betavariate(2, 5)
                b_min = float(band["min"])  # type: ignore
                b_max = float(band["max"])  # type: ignore
                amount = b_min + fraction * (b_max - b_min)

                # Start date within the last 1-24 months
                months_ago = self.py_rng.randint(1, 24)
                start_date = (customer.customer_since + timedelta(days=months_ago * 30)).date()

                # Ensure start date is not in the future
                if start_date > sim_end_date:
                    start_date = sim_end_date - timedelta(days=30)

                # Next billing date is usually exactly a month after the last cycle
                next_billing_date = start_date + timedelta(days=30)

                sub = Subscription(
                    subscription_id=uuid.UUID(int=self.py_rng.getrandbits(128)),
                    customer_id=customer.customer_id,
                    plan=band_name,
                    amount=Decimal(f"{amount:.2f}"),
                    currency="INR",
                    billing_cycle="monthly",
                    start_date=start_date,
                    next_billing_date=next_billing_date,
                    status="active",
                    created_at=datetime.combine(start_date, datetime.min.time(), tzinfo=UTC),
                    updated_at=datetime.combine(start_date, datetime.min.time(), tzinfo=UTC),
                )
                subscriptions.append(sub)

            # Generate Invoices for business customers (independent of subscriptions or tied?
            # The spec says "Business customers receive invoices with realistic skewed amounts").
            # We'll generate 1-12 historical invoices for business customers.
            if customer.customer_type == "business":
                num_invoices = self.py_rng.randint(1, 12)
                for i in range(num_invoices):
                    # Invoice amount
                    c_arch = getattr(customer, "_archetype", "RELIABLE_CONSUMER")
                    if c_arch == "SMALL_BUSINESS":
                        inv_amount = self.py_rng.uniform(5000, 100000)
                    else:
                        inv_amount = self.py_rng.uniform(50000, 1000000)

                    issue_date = (customer.customer_since + timedelta(days=30 * i)).date()
                    due_date = issue_date + timedelta(days=30)  # Net-30

                    if due_date + timedelta(days=1) >= sim_end_date:
                        break  # Do not generate invoices whose cases would fall beyond the simulation window

                    # Will it be paid?
                    # Delay is based on avg_payment_delay_days
                    delay_days = max(
                        0,
                        int(
                            self.py_rng.normalvariate(
                                float(customer.avg_payment_delay_days or 0.0), 2.0
                            )
                        ),
                    )

                    if (
                        delay_days > 0
                        and issue_date + timedelta(days=30 + delay_days) > sim_end_date
                    ):
                        # Overdue/Unpaid
                        status = "overdue"
                        paid_at = None
                        days_overdue = max(0, (sim_end_date - due_date).days)
                    else:
                        status = "paid"
                        paid_at = datetime.combine(
                            due_date + timedelta(days=delay_days), datetime.min.time(), tzinfo=UTC
                        )
                        days_overdue = 0

                    invoice = Invoice(
                        invoice_id=uuid.UUID(int=self.py_rng.getrandbits(128)),
                        customer_id=customer.customer_id,
                        amount=Decimal(f"{inv_amount:.2f}"),
                        currency="INR",
                        issue_date=issue_date,
                        due_date=due_date,
                        status=status,
                        days_overdue=days_overdue,
                        paid_at=paid_at,
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    )
                    invoices.append(invoice)

        return subscriptions, invoices
