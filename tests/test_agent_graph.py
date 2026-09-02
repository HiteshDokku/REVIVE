"""Tests for the Milestone 10 LangGraph Agent Orchestrator."""

import typing
import uuid
from typing import TYPE_CHECKING

import pytest

from src.agent.graph import graph

if TYPE_CHECKING:
    from src.agent.state import RecoveryState


def test_graph_construction() -> None:
    """Verify the graph constructs and compiles correctly."""
    assert graph is not None

    # Check that it has nodes
    nodes = [n for n in graph.nodes]
    assert "load_case" in nodes
    assert "assess_risk" in nodes
    assert "diagnose_root_cause" in nodes
    assert "generate_candidate_actions" in nodes
    assert "predict_recovery" in nodes
    assert "optimize_action" in nodes
    assert "policy_check" in nodes
    assert "execute_action" in nodes
    assert "evaluate_outcome" in nodes
    assert "close_case" in nodes
    assert "escalate" in nodes
    assert "stop_case" in nodes


def test_routing_policy_allow() -> None:
    """Test policy_check route."""
    from src.agent.graph import route_policy

    state: RecoveryState = {"policy_decision": "ALLOW"}
    assert route_policy(state) == "execute_action"


def test_routing_policy_escalate() -> None:
    from src.agent.graph import route_policy

    state: RecoveryState = {"policy_decision": "ESCALATE"}
    assert route_policy(state) == "escalate"


def test_routing_policy_deny() -> None:
    from src.agent.graph import route_policy

    state: RecoveryState = {"policy_decision": "DENY"}
    assert route_policy(state) == "stop_case"


def test_routing_outcome_recovered() -> None:
    from src.agent.graph import route_outcome

    state: RecoveryState = {"next_step": "RECOVERED"}
    assert route_outcome(state) == "close_case"


def test_routing_outcome_retryable() -> None:
    from src.agent.graph import route_outcome

    state: RecoveryState = {"next_step": "RETRYABLE"}
    assert route_outcome(state) == "generate_candidate_actions"


def test_routing_outcome_stop() -> None:
    from src.agent.graph import route_outcome

    state: RecoveryState = {"next_step": "STOP"}
    assert route_outcome(state) == "stop_case"


def test_routing_outcome_escalate() -> None:
    from src.agent.graph import route_outcome

    state: RecoveryState = {"next_step": "HUMAN_REVIEW"}
    assert route_outcome(state) == "escalate"


@pytest.fixture
def test_case_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> typing.Generator[tuple[uuid.UUID, uuid.UUID], None, None]:
    import decimal
    from datetime import UTC, datetime

    from sqlalchemy.orm import sessionmaker

    from src.database.base import Base
    from src.database.connection import get_sync_engine
    from src.database.models import Customer, Payment, RecoveryCase

    customer_id = uuid.uuid4()
    case_id = uuid.uuid4()
    payment_id = uuid.uuid4()

    engine = get_sync_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    session_factory = sessionmaker(bind=engine)

    # Patch all the nodes that imported the function directly
    nodes = [
        "src.agent.nodes.loader",
        "src.agent.nodes.risk",
        "src.agent.nodes.root_cause",
        "src.agent.nodes.candidates",
        "src.agent.nodes.propensity",
        "src.agent.nodes.decision",
        "src.agent.nodes.policy",
        "src.agent.nodes.execution",
    ]
    for node in nodes:
        monkeypatch.setattr(f"{node}.get_sync_session_factory", lambda: session_factory)

    session = session_factory()

    c = Customer(
        customer_id=customer_id,
        customer_type="INDIVIDUAL",
        country="US",
        language="en",
        city="NY",
        preferred_channel="EMAIL",
        customer_since=datetime.now(UTC),
        active_subscriptions=1,
        lifetime_value=decimal.Decimal("100.0"),
        payment_reliability_score=decimal.Decimal("0.8"),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(c)

    # Create payment
    p = Payment(
        payment_id=payment_id,
        customer_id=customer_id,
        amount=decimal.Decimal("50.0"),
        currency="USD",
        occurred_at=datetime.now(UTC),
        payment_method="card",
        gateway="stripe",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        status="failed",
    )
    session.add(p)

    # Create case
    case = RecoveryCase(
        case_id=case_id,
        customer_id=customer_id,
        source_type="payment",
        source_id=payment_id,
        amount_at_risk=decimal.Decimal("50.0"),
        status="OPEN",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        root_cause="INSUFFICIENT_FUNDS",
    )
    session.add(case)
    session.commit()

    yield case_id, customer_id


def test_end_to_end_smoke(test_case_setup: tuple[uuid.UUID, uuid.UUID]) -> None:
    """Execute a realistic failed-payment scenario through the complete M10 graph."""
    case_id, _ = test_case_setup

    initial_state: RecoveryState = {
        "case_id": str(case_id),
    }

    # Define recursion limit to prevent infinite loops (LangGraph supports recursion_limit)
    final_state = graph.invoke(initial_state, {"recursion_limit": 100})

    assert final_state is not None
    assert "audit_context" in final_state

    audit_nodes = [entry["node"] for entry in final_state["audit_context"]]

    # Check that required nodes were visited
    assert "load_case" in audit_nodes
    assert "assess_risk" in audit_nodes
    assert "diagnose_root_cause" in audit_nodes
    assert "generate_candidate_actions" in audit_nodes
    assert "predict_recovery" in audit_nodes
    assert "optimize_action" in audit_nodes
    assert "policy_check" in audit_nodes

    # We should see execution if policy allows
    if "execute_action" in audit_nodes:
        assert "evaluate_outcome" in audit_nodes

    # The graph must reach a terminal state
    terminal_nodes = {"close_case", "stop_case", "escalate"}
    assert any(node in audit_nodes for node in terminal_nodes)
