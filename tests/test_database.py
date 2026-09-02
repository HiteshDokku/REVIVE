"""Tests for the database layer including repositories and constraints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from src.database.base import Base
from src.database.models import Customer, Payment
from src.database.repositories.core import CustomerRepository, PaymentRepository

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(scope="session")
def engine() -> Generator[Engine, None, None]:
    """Create a sync SQLite in-memory engine for testing."""
    engine_obj = create_engine("sqlite:///:memory:", echo=False)

    # Enable foreign keys for SQLite
    def _fk_pragma_on_connect(dbapi_con: Any, con_record: Any) -> None:
        dbapi_con.execute("pragma foreign_keys=ON")

    from sqlalchemy import event

    event.listen(engine_obj, "connect", _fk_pragma_on_connect)

    Base.metadata.create_all(engine_obj)
    yield engine_obj
    Base.metadata.drop_all(engine_obj)


@pytest.fixture
def db_session(engine: Engine) -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    connection = engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, expire_on_commit=False)
    session = session_factory()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


def test_customer_repository_crud(db_session: Session) -> None:
    """Test creating and retrieving a customer."""
    repo = CustomerRepository(db_session)
    customer_id = uuid.uuid4()

    # Create
    new_customer = Customer(
        customer_id=customer_id,
        customer_type="individual",
        country="IN",
        language="en",
        preferred_channel="email",
        customer_since=datetime.now(UTC),
        lifetime_value=Decimal("15000.50"),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repo.create(new_customer)

    # Retrieve
    retrieved = repo.get_by_id(customer_id)
    assert retrieved is not None
    assert retrieved.country == "IN"

    # Decimal preservation
    assert retrieved.lifetime_value == Decimal("15000.50")


def test_foreign_key_constraint(db_session: Session) -> None:
    """Test that foreign keys are enforced."""
    payment_repo = PaymentRepository(db_session)

    # Attempt to create a payment with a non-existent customer
    payment = Payment(
        customer_id=uuid.uuid4(),
        amount=Decimal("100.00"),
        occurred_at=datetime.now(UTC),
        payment_method="card",
        status="failed",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with pytest.raises(IntegrityError):
        payment_repo.create(payment)
        db_session.commit()

    db_session.rollback()


def test_monetary_field_decimal_preservation(db_session: Session) -> None:
    """Test that monetary values are correctly preserved as Decimal."""
    customer_repo = CustomerRepository(db_session)
    customer_id = uuid.uuid4()
    new_customer = Customer(
        customer_id=customer_id,
        customer_type="individual",
        country="IN",
        language="en",
        preferred_channel="email",
        customer_since=datetime.now(UTC),
        lifetime_value=Decimal("15000.50"),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    customer_repo.create(new_customer)

    payment_repo = PaymentRepository(db_session)
    payment = Payment(
        customer_id=customer_id,
        amount=Decimal("199.99"),
        occurred_at=datetime.now(UTC),
        payment_method="card",
        status="failed",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    payment_repo.create(payment)

    retrieved = payment_repo.get_by_id(payment.payment_id)
    assert retrieved is not None
    assert isinstance(retrieved.amount, Decimal)
    assert retrieved.amount == Decimal("199.99")


def test_idempotency_constraint(db_session: Session) -> None:
    """Test unique constraint on idempotency_key."""
    customer_repo = CustomerRepository(db_session)
    payment_repo = PaymentRepository(db_session)

    customer_id = uuid.uuid4()
    customer_repo.create(
        Customer(
            customer_id=customer_id,
            customer_type="individual",
            country="IN",
            language="en",
            preferred_channel="email",
            customer_since=datetime.now(UTC),
            lifetime_value=Decimal("0"),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )

    payment1 = Payment(
        customer_id=customer_id,
        amount=Decimal("100.00"),
        occurred_at=datetime.now(UTC),
        payment_method="card",
        status="failed",
        idempotency_key="idem-key-123",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    payment_repo.create(payment1)

    # Try to create a second payment with the same idempotency key
    payment2 = Payment(
        customer_id=customer_id,
        amount=Decimal("200.00"),
        occurred_at=datetime.now(UTC),
        payment_method="upi",
        status="failed",
        idempotency_key="idem-key-123",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with pytest.raises(IntegrityError):
        payment_repo.create(payment2)
        db_session.commit()
