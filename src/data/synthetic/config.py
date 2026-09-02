"""Configuration for synthetic data generation."""

from typing import TypedDict


class ArchetypeConfig(TypedDict):
    """Configuration for a customer archetype."""

    weight: float
    base_reliability_alpha: float
    base_reliability_beta: float
    base_delay_mu: float
    base_delay_sigma: float
    customer_type: str
    lifetime_value_mu: float
    lifetime_value_sigma: float
    preferred_channels: list[tuple[str, float]]


class GenerationConfig:
    """Configuration for synthetic environment scaling and distributions."""

    def __init__(
        self,
        num_customers: int = 35000,
        num_months: int = 6,
        seed: int = 42,
    ) -> None:
        # Scale
        self.num_customers = num_customers
        self.num_months = num_months

        # Random seed
        self.seed = seed

        # Archetypes
        self.archetypes = {
            "RELIABLE_CONSUMER": ArchetypeConfig(
                weight=0.35,
                base_reliability_alpha=9.0,
                base_reliability_beta=1.0,
                base_delay_mu=0.5,
                base_delay_sigma=0.2,
                customer_type="individual",
                lifetime_value_mu=8.0,
                lifetime_value_sigma=0.5,
                preferred_channels=[("email", 0.6), ("sms", 0.3), ("whatsapp", 0.1)],
            ),
            "OCCASIONALLY_LATE": ArchetypeConfig(
                weight=0.25,
                base_reliability_alpha=6.0,
                base_reliability_beta=3.0,
                base_delay_mu=2.0,
                base_delay_sigma=1.0,
                customer_type="individual",
                lifetime_value_mu=7.5,
                lifetime_value_sigma=0.8,
                preferred_channels=[("whatsapp", 0.5), ("sms", 0.4), ("email", 0.1)],
            ),
            "HIGH_RISK_CONSUMER": ArchetypeConfig(
                weight=0.15,
                base_reliability_alpha=3.0,
                base_reliability_beta=5.0,
                base_delay_mu=4.0,
                base_delay_sigma=1.5,
                customer_type="individual",
                lifetime_value_mu=6.5,
                lifetime_value_sigma=1.0,
                preferred_channels=[("whatsapp", 0.7), ("voice", 0.3)],
            ),
            "PREMIUM_CUSTOMER": ArchetypeConfig(
                weight=0.10,
                base_reliability_alpha=9.5,
                base_reliability_beta=0.5,
                base_delay_mu=0.1,
                base_delay_sigma=0.1,
                customer_type="individual",
                lifetime_value_mu=10.0,
                lifetime_value_sigma=0.5,
                preferred_channels=[("email", 0.8), ("voice", 0.2)],
            ),
            "SMALL_BUSINESS": ArchetypeConfig(
                weight=0.08,
                base_reliability_alpha=7.0,
                base_reliability_beta=2.0,
                base_delay_mu=3.0,
                base_delay_sigma=1.0,
                customer_type="business",
                lifetime_value_mu=11.0,
                lifetime_value_sigma=0.6,
                preferred_channels=[("email", 0.9), ("account_manager", 0.1)],
            ),
            "MID_MARKET_BUSINESS": ArchetypeConfig(
                weight=0.05,
                base_reliability_alpha=8.0,
                base_reliability_beta=1.5,
                base_delay_mu=5.0,
                base_delay_sigma=2.0,
                customer_type="business",
                lifetime_value_mu=13.0,
                lifetime_value_sigma=0.7,
                preferred_channels=[("email", 0.7), ("account_manager", 0.3)],
            ),
            "NEW_CUSTOMER": ArchetypeConfig(
                weight=0.02,
                base_reliability_alpha=5.0,
                base_reliability_beta=5.0,
                base_delay_mu=1.0,
                base_delay_sigma=1.0,
                customer_type="individual",
                lifetime_value_mu=5.0,
                lifetime_value_sigma=1.5,
                preferred_channels=[("email", 0.5), ("sms", 0.5)],
            ),
        }

        # Subscription Bands (Consumer)
        self.consumer_subscription_bands = [
            {"name": "Basic", "min": 199, "max": 999, "weight": 0.5},
            {"name": "Standard", "min": 1000, "max": 4999, "weight": 0.35},
            {"name": "Premium", "min": 5000, "max": 25000, "weight": 0.15},
        ]

        # Subscription Bands (Business)
        self.business_subscription_bands = [
            {"name": "Business Standard", "min": 25000, "max": 100000, "weight": 0.7},
            {"name": "Business Premium", "min": 100000, "max": 200000, "weight": 0.3},
        ]

        # Failure Mechanisms — Balanced Base Weights across all 10 root causes
        self.failure_mechanisms = [
            {"reason": "TEMPORARY_ISSUER_DECLINE", "weight": 0.10, "recoverable": True},
            {"reason": "INSUFFICIENT_FUNDS", "weight": 0.10, "recoverable": True},
            {"reason": "EXPIRED_CARD", "weight": 0.10, "recoverable": True},
            {"reason": "INVALID_PAYMENT_METHOD", "weight": 0.10, "recoverable": False},
            {"reason": "GATEWAY_FAILURE", "weight": 0.10, "recoverable": True},
            {"reason": "NETWORK_TIMEOUT", "weight": 0.10, "recoverable": True},
            {"reason": "CUSTOMER_ABANDONMENT", "weight": 0.10, "recoverable": True},
            {"reason": "DUPLICATE_PAYMENT", "weight": 0.10, "recoverable": False},
            {"reason": "UNKNOWN", "weight": 0.10, "recoverable": True},
            {"reason": "OVERDUE_INVOICE", "weight": 0.10, "recoverable": True},
        ]

        # Gateways
        self.gateways = [
            {"name": "gateway_a", "base_success": 0.98, "weight": 0.5},
            {"name": "gateway_b", "base_success": 0.95, "weight": 0.3},
            {"name": "gateway_c", "base_success": 0.99, "weight": 0.2},
        ]

        # Temporal configuration
        self.start_date = "2023-01-01T00:00:00Z"
