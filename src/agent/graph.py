"""LangGraph builder for the REVIVE agent."""

from typing import Any, Literal

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agent.nodes.candidates import generate_candidate_actions
from src.agent.nodes.decision import optimize_action
from src.agent.nodes.execution import execute_action
from src.agent.nodes.loader import load_case
from src.agent.nodes.outcome import evaluate_outcome
from src.agent.nodes.policy import policy_check
from src.agent.nodes.propensity import predict_recovery
from src.agent.nodes.risk import assess_risk
from src.agent.nodes.root_cause import diagnose_root_cause
from src.agent.nodes.terminal import close_case, escalate, stop_case
from src.agent.state import RecoveryState


def route_policy(state: RecoveryState) -> Literal["execute_action", "escalate", "stop_case"]:
    """Route based on policy decision."""
    decision = state.get("policy_decision")
    if decision == "ALLOW":
        return "execute_action"
    elif decision == "ESCALATE":
        return "escalate"
    else:  # DENY or unknown
        return "stop_case"


def route_outcome(
    state: RecoveryState,
) -> Literal["close_case", "generate_candidate_actions", "stop_case", "escalate"]:
    """Route based on evaluated outcome."""
    next_step = state.get("next_step", "")
    if next_step == "RECOVERED":
        return "close_case"
    if next_step == "RETRYABLE":
        return "generate_candidate_actions"
    if next_step == "HUMAN_REVIEW":
        return "escalate"
    return "stop_case"


def build_graph() -> CompiledStateGraph[Any, Any, Any]:
    """Build and compile the LangGraph workflow."""
    builder = StateGraph(RecoveryState)

    # Add nodes
    builder.add_node("load_case", load_case)
    builder.add_node("assess_risk", assess_risk)
    builder.add_node("diagnose_root_cause", diagnose_root_cause)
    builder.add_node("generate_candidate_actions", generate_candidate_actions)
    builder.add_node("predict_recovery", predict_recovery)
    builder.add_node("optimize_action", optimize_action)
    builder.add_node("policy_check", policy_check)
    builder.add_node("execute_action", execute_action)
    builder.add_node("evaluate_outcome", evaluate_outcome)
    builder.add_node("close_case", close_case)
    builder.add_node("escalate", escalate)
    builder.add_node("stop_case", stop_case)

    # Add static edges
    builder.set_entry_point("load_case")
    builder.add_edge("load_case", "assess_risk")
    builder.add_edge("assess_risk", "diagnose_root_cause")
    builder.add_edge("diagnose_root_cause", "generate_candidate_actions")
    builder.add_edge("generate_candidate_actions", "predict_recovery")
    builder.add_edge("predict_recovery", "optimize_action")
    builder.add_edge("optimize_action", "policy_check")

    # Add conditional edge for policy
    builder.add_conditional_edges(
        "policy_check",
        route_policy,
        {
            "execute_action": "execute_action",
            "escalate": "escalate",
            "stop_case": "stop_case",
        },
    )

    # Post-execution outcome processing
    builder.add_edge("execute_action", "evaluate_outcome")

    # Add conditional edge for outcome routing
    builder.add_conditional_edges(
        "evaluate_outcome",
        route_outcome,
        {
            "close_case": "close_case",
            "generate_candidate_actions": "generate_candidate_actions",
            "stop_case": "stop_case",
            "escalate": "escalate",
        },
    )

    # Terminal edges
    builder.add_edge("close_case", END)
    builder.add_edge("escalate", END)
    builder.add_edge("stop_case", END)

    return builder.compile()


# Provide a compiled default instance
graph = build_graph()
