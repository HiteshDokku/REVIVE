"""Configuration for the Policy and Guardrails layer."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class GuardrailConfig(BaseModel):
    """Configuration for policy threshold and limit guardrails."""

    max_payment_retries: int = Field(default=2, ge=0)
    min_retry_cooldown_hours: int = Field(default=12, ge=0)
    max_recovery_window_days: int = Field(default=14, ge=0)

    max_customer_contacts: int = Field(default=3, ge=0)
    min_contact_cooldown_hours: int = Field(default=24, ge=0)

    high_value_threshold: Decimal = Field(default=Decimal("9999999.00"), ge=0)
    min_expected_net_recovery: Decimal = Field(default=Decimal("0.01"), ge=0)

    model_config = ConfigDict(frozen=True)
