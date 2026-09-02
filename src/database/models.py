"""SQLAlchemy ORM models implementing the REVIVE database schema.

All tables, columns, constraints, indexes, and relationships are
defined exactly as specified in SCHEMA.md.

Key design decisions:
- UUID primary keys
- UTC timestamps (TIMESTAMPTZ)
- Monetary values use Numeric(18,2), Python Decimal
- Probability/confidence values use Numeric(6,5)
- CHECK constraints modeled via CheckConstraint
- Partial unique indexes use Index with postgresql_where
"""

from __future__ import annotations

import uuid
from datetime import date, datetime  # noqa: TC003
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base

JSONVariant = JSON().with_variant(JSONB, "postgresql")


# ---------------------------------------------------------------------------
# customers
# ---------------------------------------------------------------------------
class Customer(Base):
    """Customer entity — the root of most domain relationships."""

    __tablename__ = "customers"

    customer_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_type: Mapped[str] = mapped_column(String(32), nullable=False)
    country: Mapped[str] = mapped_column(String(64), nullable=False)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    preferred_channel: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_since: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payment_reliability_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 5), nullable=True)
    avg_payment_delay_days: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    lifetime_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    active_subscriptions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    communication_opt_out: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    subscriptions: Mapped[list[Subscription]] = relationship(back_populates="customer")
    payments: Mapped[list[Payment]] = relationship(back_populates="customer")
    invoices: Mapped[list[Invoice]] = relationship(back_populates="customer")
    interactions: Mapped[list[Interaction]] = relationship(back_populates="customer")
    recovery_cases: Mapped[list[RecoveryCase]] = relationship(back_populates="customer")

    __table_args__ = (
        CheckConstraint(
            "payment_reliability_score IS NULL OR "
            "(payment_reliability_score >= 0 AND payment_reliability_score <= 1)",
            name="ck_customers_reliability_score_range",
        ),
        CheckConstraint("lifetime_value >= 0", name="ck_customers_lifetime_value_non_negative"),
        CheckConstraint(
            "active_subscriptions >= 0", name="ck_customers_active_subscriptions_non_negative"
        ),
    )


# ---------------------------------------------------------------------------
# subscriptions
# ---------------------------------------------------------------------------
class Subscription(Base):
    """Subscription entity linked to a customer."""

    __tablename__ = "subscriptions"

    subscription_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.customer_id"), nullable=False
    )
    plan: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    billing_cycle: Mapped[str] = mapped_column(String(32), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    next_billing_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    customer: Mapped[Customer] = relationship(back_populates="subscriptions")
    payments: Mapped[list[Payment]] = relationship(back_populates="subscription")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_subscriptions_amount_positive"),
        CheckConstraint(
            "next_billing_date >= start_date", name="ck_subscriptions_billing_after_start"
        ),
    )


# ---------------------------------------------------------------------------
# payments
# ---------------------------------------------------------------------------
class Payment(Base):
    """Payment event with gateway, status, failure info, and idempotency."""

    __tablename__ = "payments"

    payment_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.customer_id"), nullable=False
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("subscriptions.subscription_id"), nullable=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(32), nullable=False)
    gateway: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # New observable telemetry fields
    card_expiry_remaining_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gateway_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checkout_session_duration_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_international: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)

    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    customer: Mapped[Customer] = relationship(back_populates="payments")
    subscription: Mapped[Subscription | None] = relationship(back_populates="payments")
    recovery_cases: Mapped[list[RecoveryCase]] = relationship(
        back_populates="source_payment",
        foreign_keys="RecoveryCase.source_id",
        primaryjoin="Payment.payment_id == foreign(RecoveryCase.source_id)",
        viewonly=True,
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        CheckConstraint("retry_count >= 0", name="ck_payments_retry_count_non_negative"),
        # Partial unique index on idempotency_key (PostgreSQL-specific)
        Index(
            "uq_payments_idempotency",
            "idempotency_key",
            unique=True,
            postgresql_where="idempotency_key IS NOT NULL",
        ),
        Index("idx_payments_customer_time", "customer_id", occurred_at.desc()),
        Index("idx_payments_status", "status"),
        Index("idx_payments_gateway_time", "gateway", occurred_at.desc()),
    )


# ---------------------------------------------------------------------------
# invoices
# ---------------------------------------------------------------------------
class Invoice(Base):
    """Invoice entity with due-date tracking."""

    __tablename__ = "invoices"

    invoice_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.customer_id"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    days_overdue: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    customer: Mapped[Customer] = relationship(back_populates="invoices")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_invoices_amount_positive"),
        CheckConstraint("due_date >= issue_date", name="ck_invoices_due_after_issue"),
        CheckConstraint("days_overdue >= 0", name="ck_invoices_days_overdue_non_negative"),
        Index("idx_invoices_customer", "customer_id"),
        Index("idx_invoices_status_due", "status", "due_date"),
    )


# ---------------------------------------------------------------------------
# recovery_cases
# ---------------------------------------------------------------------------
class RecoveryCase(Base):
    """Central recovery case linking a revenue event to interventions and outcomes."""

    __tablename__ = "recovery_cases"

    case_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.customer_id"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    amount_at_risk: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    risk_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 5), nullable=True)
    root_cause: Mapped[str | None] = mapped_column(String(64), nullable=True)
    root_cause_confidence: Mapped[Decimal | None] = mapped_column(Numeric(6, 5), nullable=True)
    recovery_probability: Mapped[Decimal | None] = mapped_column(Numeric(6, 5), nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expected_recovery: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    expected_net_recovery: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    decision_confidence: Mapped[Decimal | None] = mapped_column(Numeric(6, 5), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    escalation_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    stop_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    workflow_run_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    customer: Mapped[Customer] = relationship(back_populates="recovery_cases")
    interventions: Mapped[list[Intervention]] = relationship(back_populates="recovery_case")
    outcomes: Mapped[list[Outcome]] = relationship(back_populates="recovery_case")
    audit_events: Mapped[list[AuditEvent]] = relationship(back_populates="recovery_case")
    # Viewonly relationship back to payment source
    source_payment: Mapped[Payment | None] = relationship(
        foreign_keys=[source_id],
        primaryjoin="RecoveryCase.source_id == Payment.payment_id",
        viewonly=True,
    )

    __table_args__ = (
        CheckConstraint(
            "amount_at_risk >= 0", name="ck_recovery_cases_amount_at_risk_non_negative"
        ),
        CheckConstraint(
            "risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 1)",
            name="ck_recovery_cases_risk_score_range",
        ),
        CheckConstraint(
            "root_cause_confidence IS NULL OR "
            "(root_cause_confidence >= 0 AND root_cause_confidence <= 1)",
            name="ck_recovery_cases_root_cause_confidence_range",
        ),
        CheckConstraint(
            "recovery_probability IS NULL OR "
            "(recovery_probability >= 0 AND recovery_probability <= 1)",
            name="ck_recovery_cases_recovery_probability_range",
        ),
        CheckConstraint(
            "decision_confidence IS NULL OR "
            "(decision_confidence >= 0 AND decision_confidence <= 1)",
            name="ck_recovery_cases_decision_confidence_range",
        ),
        CheckConstraint(
            "expected_recovery IS NULL OR expected_recovery >= 0",
            name="ck_recovery_cases_expected_recovery_non_negative",
        ),
        CheckConstraint(
            "expected_net_recovery IS NULL OR expected_net_recovery >= 0",
            name="ck_recovery_cases_expected_net_recovery_non_negative",
        ),
        # Partial unique index: one active case per source
        Index(
            "uq_active_recovery_case",
            "source_type",
            "source_id",
            unique=True,
            postgresql_where="status NOT IN ('CLOSED','CANCELLED')",
        ),
        Index("idx_cases_status_priority", "status", expected_net_recovery.desc()),
        Index("idx_cases_customer", "customer_id"),
        Index("idx_cases_source", "source_type", "source_id"),
    )


# ---------------------------------------------------------------------------
# interactions
# ---------------------------------------------------------------------------
class Interaction(Base):
    """Customer interaction (communications) linked to a customer and optionally a case."""

    __tablename__ = "interactions"

    interaction_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.customer_id"), nullable=False
    )
    recovery_case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("recovery_cases.case_id"), nullable=True
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    customer_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    promise_to_pay: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    promised_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    llm_confidence: Mapped[Decimal | None] = mapped_column(Numeric(6, 5), nullable=True)
    generation_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    customer: Mapped[Customer] = relationship(back_populates="interactions")

    __table_args__ = (
        Index("idx_interactions_customer_time", "customer_id", occurred_at.desc()),
        Index("idx_interactions_case_time", "recovery_case_id", occurred_at.desc()),
    )


# ---------------------------------------------------------------------------
# interventions
# ---------------------------------------------------------------------------
class Intervention(Base):
    """An intervention action on a recovery case with idempotency enforcement."""

    __tablename__ = "interventions"

    intervention_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recovery_cases.case_id"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    policy_decision: Mapped[str] = mapped_column(String(16), nullable=False)
    policy_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    recovery_case: Mapped[RecoveryCase] = relationship(back_populates="interventions")
    outcomes: Mapped[list[Outcome]] = relationship(back_populates="intervention")

    __table_args__ = (
        CheckConstraint("attempt_number >= 1", name="ck_interventions_attempt_number_min"),
        CheckConstraint("cost >= 0", name="ck_interventions_cost_non_negative"),
    )


# ---------------------------------------------------------------------------
# outcomes
# ---------------------------------------------------------------------------
class Outcome(Base):
    """Result of an intervention, recording success/failure and amount recovered."""

    __tablename__ = "outcomes"

    outcome_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recovery_cases.case_id"), nullable=False)
    intervention_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interventions.intervention_id"), nullable=False
    )
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    amount_recovered: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0")
    )
    failure_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payment_status_after: Mapped[str | None] = mapped_column(String(32), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    recovery_case: Mapped[RecoveryCase] = relationship(back_populates="outcomes")
    intervention: Mapped[Intervention] = relationship(back_populates="outcomes")

    __table_args__ = (
        CheckConstraint("amount_recovered >= 0", name="ck_outcomes_amount_recovered_non_negative"),
    )


# ---------------------------------------------------------------------------
# audit_events
# ---------------------------------------------------------------------------
class AuditEvent(Base):
    """Append-only audit log for recovery decisions and actions."""

    __tablename__ = "audit_events"

    event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("recovery_cases.case_id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # JSONB columns — fallback to JSON type for non-PostgreSQL backends
    input_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONVariant, nullable=True)
    decision: Mapped[dict[str, Any] | None] = mapped_column(JSONVariant, nullable=True)
    policy_result: Mapped[dict[str, Any] | None] = mapped_column(JSONVariant, nullable=True)
    execution_result: Mapped[dict[str, Any] | None] = mapped_column(JSONVariant, nullable=True)
    outcome: Mapped[dict[str, Any] | None] = mapped_column(JSONVariant, nullable=True)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONVariant, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    recovery_case: Mapped[RecoveryCase | None] = relationship(back_populates="audit_events")

    __table_args__ = (
        Index("idx_audit_case_time", "case_id", event_time.desc()),
        Index("idx_audit_correlation", "correlation_id"),
    )


# ---------------------------------------------------------------------------
# simulation_runs
# ---------------------------------------------------------------------------
class SimulationRun(Base):
    """Record of a simulation run with strategy, scenario, and seed."""

    __tablename__ = "simulation_runs"

    run_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    strategy: Mapped[str] = mapped_column(String(64), nullable=False)
    scenario: Mapped[str] = mapped_column(String(64), nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    model_versions: Mapped[dict[str, Any] | None] = mapped_column(JSONVariant, nullable=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    configuration_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)

    # Relationships
    results: Mapped[list[SimulationResult]] = relationship(back_populates="simulation_run")
    model_runs: Mapped[list[ModelRun]] = relationship(back_populates="simulation_run")


# ---------------------------------------------------------------------------
# simulation_results
# ---------------------------------------------------------------------------
class SimulationResult(Base):
    """Aggregated financial/safety results from a simulation run."""

    __tablename__ = "simulation_results"

    result_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("simulation_runs.run_id"), nullable=False)
    total_events: Mapped[int] = mapped_column(Integer, nullable=False)
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    revenue_at_risk: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    gross_recovered: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    intervention_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    net_recovered: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    recovery_rate: Mapped[Decimal] = mapped_column(Numeric(8, 5), nullable=False)
    incremental_revenue: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    policy_violations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_actions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    escalations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stopped_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recovered_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    simulation_run: Mapped[SimulationRun] = relationship(back_populates="results")


# ---------------------------------------------------------------------------
# model_metadata
# ---------------------------------------------------------------------------
class ModelMetadata(Base):
    """Metadata for a trained ML model artifact."""

    __tablename__ = "model_metadata"

    model_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    model_type: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    training_dataset_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    artifact_uri: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONVariant, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    model_runs: Mapped[list[ModelRun]] = relationship(back_populates="model")

    __table_args__ = (
        UniqueConstraint("model_name", "model_version", name="uq_model_name_version"),
    )


# ---------------------------------------------------------------------------
# model_runs
# ---------------------------------------------------------------------------
class ModelRun(Base):
    """Record of model inference usage within a simulation run."""

    __tablename__ = "model_runs"

    model_run_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    model_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("model_metadata.model_id"), nullable=False
    )
    simulation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("simulation_runs.run_id"), nullable=True
    )
    inference_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    average_latency_ms: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    model: Mapped[ModelMetadata] = relationship(back_populates="model_runs")
    simulation_run: Mapped[SimulationRun | None] = relationship(back_populates="model_runs")
