"""Tests for UI fixes related to fault injection and metric semantics."""

import os
import tempfile
import typing
import uuid
from decimal import Decimal
from datetime import datetime, UTC
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from streamlit.testing.v1 import AppTest

from src.database.base import Base
from src.database.models import Customer, RecoveryCase


@pytest.fixture(autouse=True)
def mock_db() -> typing.Generator[sessionmaker, None, None]:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    
    with patch("src.database.connection.get_sync_session_factory", return_value=session_factory):
        # We also need to patch for the node execution
        nodes = [
            "src.agent.nodes.loader",
            "src.agent.nodes.risk",
            "src.agent.nodes.root_cause",
            "src.agent.nodes.candidates",
            "src.agent.nodes.propensity",
            "src.agent.nodes.decision",
            "src.agent.nodes.policy",
            "src.agent.nodes.execution",
            "frontend.app"
        ]
        with patch.multiple(
            "src.database.connection", 
            get_sync_session_factory=lambda: session_factory
        ):
            # Seed the database
            with session_factory() as session:
                # Case 1: Opted out, high amount
                c1 = Customer(
                    customer_id=uuid.uuid4(),
                    customer_type="INDIVIDUAL",
                    country="US",
                    language="en",
                    city="NY",
                    preferred_channel="EMAIL",
                    communication_opt_out=True,
                    payment_reliability_score=Decimal("0.5"),
                    lifetime_value=Decimal("100.0"),
                    active_subscriptions=1,
                    customer_since=datetime.now(UTC),
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC)
                )
                case1 = RecoveryCase(
                    case_id=uuid.uuid4(),
                    customer_id=c1.customer_id,
                    source_type="payment",
                    source_id=uuid.uuid4(),
                    amount_at_risk=Decimal("1500.0"),
                    status="OPEN",
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC)
                )
                
                # Case 2: Not opted out, moderate amount (Perfect for execution)
                c2 = Customer(
                    customer_id=uuid.uuid4(),
                    customer_type="INDIVIDUAL",
                    country="US",
                    language="en",
                    city="NY",
                    preferred_channel="EMAIL",
                    communication_opt_out=False,
                    payment_reliability_score=Decimal("0.9"),
                    lifetime_value=Decimal("100.0"),
                    active_subscriptions=1,
                    customer_since=datetime.now(UTC),
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC)
                )
                case2 = RecoveryCase(
                    case_id=uuid.uuid4(),
                    customer_id=c2.customer_id,
                    source_type="payment",
                    source_id=uuid.uuid4(),
                    amount_at_risk=Decimal("100.0"),
                    status="OPEN",
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC)
                )
                
                session.add_all([c1, case1, c2, case2])
                session.commit()
                
            yield session_factory
            
    try:
        os.remove(path)
    except OSError:
        pass


def test_fault_selection_logic_not_hardcoded(mock_db: sessionmaker) -> None:
    """Test that the right case is selected for the right fault (Points 1-9)."""
    # Test GATEWAY_OUTAGE uses the execution-ready case (case2)
    at = AppTest.from_file("../frontend/app.py")
    at.run()
    
    # Select GATEWAY_OUTAGE
    at.selectbox[0].set_value("GATEWAY_OUTAGE")
    at.button[2].click().run(timeout=30)
    
    # It should say PASS, and should NOT reach DENY
    assert "Result: PASS" in at.markdown[-1].value
    assert "Policy: ALLOW" in at.markdown[-1].value
    assert "Action Execution: REACHED" in at.markdown[-1].value

    # Select CUSTOMER_OPT_OUT
    at.selectbox[0].set_value("CUSTOMER_OPT_OUT")
    at.button[2].click().run(timeout=30)
    
    # It should say PASS and reach DENY
    assert "Result: PASS" in at.markdown[-1].value
    assert "Policy: DENY" in at.markdown[-1].value
    assert "Action Execution: NOT REACHED" in at.markdown[-1].value
    
    # Verify different fault runs correctly
    at.selectbox[0].set_value("API_TIMEOUT")
    at.button[2].click().run(timeout=30)
    assert "Result: PASS" in at.markdown[-1].value
    assert "Execution: FAILED" in at.markdown[-1].value

    at.selectbox[0].set_value("DUPLICATE_EVENT")
    at.button[2].click().run(timeout=30)
    assert "Result: PASS" in at.markdown[-1].value
    
    at.selectbox[0].set_value("ALREADY_PAID")
    at.button[2].click().run(timeout=30)
    assert "Result: PASS" in at.markdown[-1].value
    
    at.selectbox[0].set_value("POLICY_UNAVAILABLE")
    at.button[1].click().run()
    assert "Result: PASS" in at.markdown[-1].value
    assert "Forced DENY" in at.markdown[-1].value
    
    at.selectbox[0].set_value("MODEL_UNAVAILABLE")
    at.button[1].click().run()
    assert "Result: PASS" in at.markdown[-1].value
    assert "Fallback applied" in at.markdown[-1].value
    
    at.selectbox[0].set_value("LLM_UNAVAILABLE")
    at.button[1].click().run()
    assert "Result: PASS" in at.markdown[-1].value


def test_simulation_metric_delta_semantics() -> None:
    """Test metric delta formatting (Points 10-13)."""
    # The UI should format delta string with negative sign followed by number and currency.
    # We test it by running simulation lab page and checking the metric values.
    # Note: the test just verifies the script evaluates without error and metric format is applied.
    # Because we don't have mock data for M11 report in this test context, we will patch it.
    
    m11_mock_data = {
        "aggregated": {
            "ALWAYS_RETRY": {
                "total_net_recovery": {"mean": "1000"},
                "total_intervention_cost": {"mean": "2000"},
                "recovery_rate": {"mean": "0.1"},
                "total_amount_recovered": {"mean": "3000"},
            },
            "REVIVE": {
                "total_net_recovery": {"mean": "5000"},
                "total_intervention_cost": {"mean": "500"},  # Cost is lower (better)
                "recovery_rate": {"mean": "0.5"},
                "total_amount_recovered": {"mean": "5500"},
            }
        }
    }
    
    with patch("json.load", return_value=m11_mock_data):
        at = AppTest.from_file("../frontend/pages/3_simulation_lab.py")
        at.run()
        
        # Check Intervention Cost (B) which is metric[3] (index 3)
        # Cost B (500) < Cost A (2000), so diff is -1500.
        # String should be "-1,500.00 ₹"
        cost_metric_b = None
        for m in at.metric:
            if m.label == "Intervention Cost (B)":
                cost_metric_b = m
                break
                
        assert cost_metric_b is not None
        assert cost_metric_b.delta == "-1,500.00 ₹"
