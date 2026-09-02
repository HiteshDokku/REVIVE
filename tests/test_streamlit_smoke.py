"""Smoke tests for Streamlit UI using AppTest framework."""

import os
import tempfile
import typing
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from streamlit.testing.v1 import AppTest

from src.database.base import Base
from src.database.models import (  # noqa: F401
    AuditEvent,
    Customer,
    Intervention,
    Outcome,
    RecoveryCase,
)


@pytest.fixture(autouse=True)
def mock_db() -> typing.Generator[None, None, None]:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with patch("src.database.connection.get_sync_session_factory", return_value=session_factory):
        yield
    try:
        os.remove(path)
    except OSError:
        pass


def test_app_page_smoke() -> None:
    """Test that the main app page runs without errors."""
    at = AppTest.from_file("../frontend/app.py")
    at.run(timeout=10)
    assert not at.exception, f"App page raised exception: {at.exception}"


def test_recovery_cases_page_smoke() -> None:
    """Test that the recovery cases page runs without errors."""
    at = AppTest.from_file("../frontend/pages/1_recovery_cases.py")
    at.run(timeout=10)
    assert not at.exception, f"Recovery cases page raised exception: {at.exception}"


def test_decision_trace_page_smoke() -> None:
    """Test that the decision trace page runs without errors."""
    at = AppTest.from_file("../frontend/pages/2_decision_trace.py")
    at.run(timeout=10)
    assert not at.exception, f"Decision trace page raised exception: {at.exception}"


def test_simulation_lab_page_smoke() -> None:
    """Test that the simulation lab page runs without errors."""
    at = AppTest.from_file("../frontend/pages/3_simulation_lab.py")
    at.run(timeout=10)
    assert not at.exception, f"Simulation lab page raised exception: {at.exception}"


def test_audit_explorer_page_smoke() -> None:
    """Test that the audit explorer page runs without errors."""
    at = AppTest.from_file("../frontend/pages/4_audit_explorer.py")
    at.run(timeout=10)
    assert not at.exception, f"Audit explorer page raised exception: {at.exception}"


def test_model_performance_page_smoke() -> None:
    """Test that the model performance page runs without errors."""
    at = AppTest.from_file("../frontend/pages/5_model_performance.py")
    at.run(timeout=10)
    assert not at.exception, f"Model performance page raised exception: {at.exception}"
