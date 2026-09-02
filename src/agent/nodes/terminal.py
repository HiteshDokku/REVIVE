"""Terminal nodes for the LangGraph agent."""

from typing import Any

from src.agent.state import RecoveryState


def close_case(state: RecoveryState) -> dict[str, Any]:
    """Persists final state and financial outcome."""
    audit_entry = {"node": "close_case", "status": "RECOVERED"}
    current_audit = state.get("audit_context", [])
    return {
        "audit_context": [*current_audit, audit_entry],
    }


def escalate(state: RecoveryState) -> dict[str, Any]:
    """Creates a human-review task and ends autonomous execution."""
    audit_entry = {"node": "escalate", "status": "HUMAN_REVIEW"}
    current_audit = state.get("audit_context", [])
    return {
        "audit_context": [*current_audit, audit_entry],
    }


def stop_case(state: RecoveryState) -> dict[str, Any]:
    """Records block and stops execution."""
    audit_entry = {"node": "stop_case", "status": "STOPPED"}
    current_audit = state.get("audit_context", [])
    return {
        "audit_context": [*current_audit, audit_entry],
    }
