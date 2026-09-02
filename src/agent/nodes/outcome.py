"""Evaluate outcome node for the LangGraph agent."""

from typing import Any

from src.agent.state import RecoveryState


def evaluate_outcome(state: RecoveryState) -> dict[str, Any]:
    """Parse execution result and determine next routing step."""
    exec_result = state.get("execution_result", {})
    success = exec_result.get("success", False)
    action = state.get("selected_action")

    if action == "NO_ACTION":
        next_step = "STOP"
        stop_reason = "NO_ACTION_SELECTED"
    elif success:
        if action == "RETRY_LATER":
            next_step = "RECOVERED"
            stop_reason = "PAYMENT_SUCCESSFUL"
        else:
            next_step = "RETRYABLE"
            stop_reason = ""
    else:
        next_step = "RETRYABLE"
        stop_reason = ""

    audit_entry = {
        "node": "evaluate_outcome",
        "next_step": next_step,
        "stop_reason": stop_reason,
    }

    current_audit = state.get("audit_context", [])

    return {
        "next_step": next_step,
        "stop_reason": stop_reason,
        "attempt_number": state.get("attempt_number", 1) + 1,
        "audit_context": [*current_audit, audit_entry],
    }
