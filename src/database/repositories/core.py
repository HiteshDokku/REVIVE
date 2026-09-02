"""Specific repositories for core REVIVE models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from src.database.models import (
    AuditEvent,
    Customer,
    Interaction,
    Intervention,
    Invoice,
    ModelMetadata,
    ModelRun,
    Outcome,
    Payment,
    RecoveryCase,
    SimulationResult,
    SimulationRun,
    Subscription,
)
from src.database.repositories.base import CrudRepository

if TYPE_CHECKING:
    import uuid


class CustomerRepository(CrudRepository[Customer]):
    """Repository for Customer entities."""

    model_class = Customer


class SubscriptionRepository(CrudRepository[Subscription]):
    """Repository for Subscription entities."""

    model_class = Subscription


class PaymentRepository(CrudRepository[Payment]):
    """Repository for Payment entities."""

    model_class = Payment

    def get_by_idempotency_key(self, idempotency_key: str) -> Payment | None:
        """Find a payment by its idempotency key."""
        stmt = select(Payment).where(Payment.idempotency_key == idempotency_key)
        return self._session.scalars(stmt).first()


class InvoiceRepository(CrudRepository[Invoice]):
    """Repository for Invoice entities."""

    model_class = Invoice


class RecoveryCaseRepository(CrudRepository[RecoveryCase]):
    """Repository for RecoveryCase entities."""

    model_class = RecoveryCase

    def get_active_case_by_source(
        self, source_type: str, source_id: uuid.UUID
    ) -> RecoveryCase | None:
        """Find an active case for a given source."""
        stmt = select(RecoveryCase).where(
            RecoveryCase.source_type == source_type,
            RecoveryCase.source_id == source_id,
            RecoveryCase.status.notin_(["CLOSED", "CANCELLED"]),
        )
        return self._session.scalars(stmt).first()


class InteractionRepository(CrudRepository[Interaction]):
    """Repository for Interaction entities."""

    model_class = Interaction


class InterventionRepository(CrudRepository[Intervention]):
    """Repository for Intervention entities."""

    model_class = Intervention

    def get_by_idempotency_key(self, idempotency_key: str) -> Intervention | None:
        """Find an intervention by its idempotency key."""
        stmt = select(Intervention).where(Intervention.idempotency_key == idempotency_key)
        return self._session.scalars(stmt).first()


class OutcomeRepository(CrudRepository[Outcome]):
    """Repository for Outcome entities."""

    model_class = Outcome


class AuditEventRepository(CrudRepository[AuditEvent]):
    """Repository for AuditEvent entities."""

    model_class = AuditEvent

    def list_by_correlation_id(self, correlation_id: str) -> list[AuditEvent]:
        """List audit events for a correlation ID."""
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.correlation_id == correlation_id)
            .order_by(AuditEvent.event_time.desc())
        )
        return list(self._session.scalars(stmt).all())


class SimulationRunRepository(CrudRepository[SimulationRun]):
    """Repository for SimulationRun entities."""

    model_class = SimulationRun


class SimulationResultRepository(CrudRepository[SimulationResult]):
    """Repository for SimulationResult entities."""

    model_class = SimulationResult


class ModelMetadataRepository(CrudRepository[ModelMetadata]):
    """Repository for ModelMetadata entities."""

    model_class = ModelMetadata


class ModelRunRepository(CrudRepository[ModelRun]):
    """Repository for ModelRun entities."""

    model_class = ModelRun
