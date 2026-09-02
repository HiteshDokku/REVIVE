import typing

"""Unit tests for the UI Service."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.services.ui_service import (
    get_audit_logs,
    get_case_detail,
    get_decision_trace,
    get_kpi_metrics,
    get_revenue_funnel,
    get_top_opportunities,
)
from src.database.base import Base
from src.database.models import Customer, Intervention, Outcome, RecoveryCase


@pytest.fixture(scope="session")
def engine() -> typing.Iterator[typing.Any]:
    engine_obj = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine_obj)
    yield engine_obj
    Base.metadata.drop_all(engine_obj)


@pytest.fixture
def db_session(engine: typing.Any) -> typing.Iterator[typing.Any]:
    connection = engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, expire_on_commit=False)
    session = session_factory()
    yield session
    session.close()
    transaction.rollback()


def test_get_kpi_metrics(db_session: typing.Any) -> None:
    """Test KPI metrics aggregation."""
    # Create test data
    c = Customer(
        customer_id=uuid.uuid4(),
        customer_type="B2C",
        country="IN",
        language="EN",
        preferred_channel="EMAIL",
        lifetime_value=Decimal("1000.00"),
        customer_since=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(c)
    db_session.flush()

    case = RecoveryCase(
        case_id=uuid.uuid4(),
        customer_id=c.customer_id,
        source_type="PAYMENT",
        source_id=uuid.uuid4(),
        amount_at_risk=Decimal("100.00"),
        expected_net_recovery=Decimal("80.00"),
        status="OPEN",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(case)
    db_session.flush()

    intervention = Intervention(
        intervention_id=uuid.uuid4(),
        case_id=case.case_id,
        action_type="EMAIL_REMINDER",
        attempt_number=1,
        cost=Decimal("0.05"),
        policy_decision="DENY",
        policy_version="1.0",
        status="BLOCKED",
        idempotency_key="test-key",
        created_at=datetime.now(UTC),
    )
    db_session.add(intervention)
    db_session.flush()

    outcome = Outcome(
        outcome_id=uuid.uuid4(),
        case_id=case.case_id,
        intervention_id=intervention.intervention_id,
        success=True,
        amount_recovered=Decimal("100.00"),
        occurred_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    db_session.add(outcome)

    kpis = get_kpi_metrics(db_session)
    assert kpis["revenue_at_risk"] == Decimal("100.00")
    assert kpis["expected_recovery"] == Decimal("80.00")
    assert kpis["recovered_revenue"] == Decimal("100.00")
    assert kpis["active_cases"] == 1
    assert kpis["policy_blocks"] >= 0


def test_get_revenue_funnel(db_session: typing.Any) -> None:
    """Test revenue funnel aggregation."""
    funnel = get_revenue_funnel(db_session)
    assert isinstance(funnel["revenue_events"], int)
    assert isinstance(funnel["actionable_cases"], int)
    assert isinstance(funnel["approved_interventions"], int)
    assert isinstance(funnel["successful_recoveries"], int)


def test_get_top_opportunities(db_session: typing.Any) -> None:
    """Test top opportunities query."""
    opps = get_top_opportunities(db_session, limit=5)
    assert isinstance(opps, list)


def test_get_case_detail_invalid_uuid(db_session: typing.Any) -> None:
    """Test case detail with invalid UUID."""
    assert get_case_detail(db_session, "invalid-uuid") is None


def test_get_decision_trace_invalid_uuid(db_session: typing.Any) -> None:
    """Test decision trace with invalid UUID."""
    assert get_decision_trace(db_session, "invalid-uuid") == []


def test_get_audit_logs(db_session: typing.Any) -> None:
    """Test audit logs extraction."""
    logs = get_audit_logs(db_session, limit=5)
    assert isinstance(logs, list)
