"""UI Read Service to provide data for the Streamlit frontend.

This service acts as a Backend-For-Frontend (BFF), querying the SQLAlchemy
session and formatting data for Streamlit to consume without duplicating
business logic.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from src.database.models import (
    AuditEvent,
    Customer,
    Intervention,
    Outcome,
    RecoveryCase,
)

# Attempt to load the M11 artifacts
try:
    with open("artifacts/evaluations/m11_financial_report.json") as f:
        M11_REPORT = json.load(f)
except Exception:
    M11_REPORT = {}


def get_kpi_metrics(session: Session) -> dict[str, Any]:
    """Retrieve high-level KPI metrics for the Control Tower."""
    # 1. Revenue at Risk (Active Cases)
    stmt_at_risk = select(func.sum(RecoveryCase.amount_at_risk)).where(
        RecoveryCase.status.in_(["OPEN", "IN_PROGRESS"])
    )
    revenue_at_risk = session.scalars(stmt_at_risk).first() or Decimal("0.00")

    # 2. Expected Recovery (from Decision Engine predictions on active cases)
    stmt_expected = select(func.sum(RecoveryCase.expected_net_recovery)).where(
        RecoveryCase.status.in_(["OPEN", "IN_PROGRESS"])
    )
    expected_recovery = session.scalars(stmt_expected).first() or Decimal("0.00")

    # 3. Recovered Revenue (from successful outcomes)
    stmt_recovered = select(func.sum(Outcome.amount_recovered)).where(Outcome.success == True)
    recovered_revenue = session.scalars(stmt_recovered).first() or Decimal("0.00")

    # 4. Incremental Revenue (We can use REVIVE vs ALWAYS_RETRY from M11 report for demo)
    # If the report is available, extract the incremental lift
    incremental_revenue = Decimal("0.00")
    if M11_REPORT and "aggregated" in M11_REPORT:
        revive_net = Decimal(
            M11_REPORT["aggregated"]
            .get("REVIVE", {})
            .get("total_net_recovery", {})
            .get("mean", "0")
        )
        baseline_net = Decimal(
            M11_REPORT["aggregated"]
            .get("ALWAYS_RETRY", {})
            .get("total_net_recovery", {})
            .get("mean", "0")
        )
        if revive_net > 0:
            incremental_revenue = revive_net - baseline_net

    # 5. Active Recovery Cases
    stmt_active = select(func.count(RecoveryCase.case_id)).where(
        RecoveryCase.status.in_(["OPEN", "IN_PROGRESS"])
    )
    active_cases = session.scalars(stmt_active).first() or 0

    # 6. Policy Blocks
    from sqlalchemy import String, cast

    stmt_blocks = select(func.count(func.distinct(AuditEvent.case_id))).where(
        AuditEvent.event_type == "policy_check",
        cast(AuditEvent.metadata_, String).like('%"policy_decision": "DENY"%'),
    )
    policy_blocks = session.scalars(stmt_blocks).first() or 0

    return {
        "revenue_at_risk": revenue_at_risk,
        "expected_recovery": expected_recovery,
        "recovered_revenue": recovered_revenue,
        "incremental_revenue": incremental_revenue,
        "active_cases": active_cases,
        "policy_blocks": policy_blocks,
    }


def get_revenue_funnel(session: Session) -> dict[str, int]:
    """Retrieve counts for the revenue funnel."""
    # Revenue events = all cases
    revenue_events = session.scalars(select(func.count(RecoveryCase.case_id))).first() or 0

    # Actionable cases = cases not closed/cancelled
    actionable = (
        session.scalars(
            select(func.count(RecoveryCase.case_id)).where(
                RecoveryCase.status.notin_(["CLOSED", "CANCELLED"])
            )
        ).first()
        or 0
    )

    # Approved Interventions = Interventions with policy_decision != DENY
    approved = (
        session.scalars(
            select(func.count(Intervention.intervention_id)).where(
                Intervention.policy_decision != "DENY"
            )
        ).first()
        or 0
    )

    # Successful Recoveries = Outcomes with success == True
    successful = (
        session.scalars(
            select(func.count(Outcome.outcome_id)).where(Outcome.success == True)
        ).first()
        or 0
    )

    return {
        "revenue_events": revenue_events,
        "actionable_cases": actionable,
        "approved_interventions": approved,
        "successful_recoveries": successful,
    }


def get_top_opportunities(session: Session, limit: int = 10) -> list[dict[str, Any]]:
    """Retrieve the top actionable cases sorted by expected net recovery."""
    from src.database.models import Outcome

    # Use a scalar subquery for total amount recovered per case
    subq = (
        select(func.sum(Outcome.amount_recovered))
        .where(Outcome.case_id == RecoveryCase.case_id)
        .correlate(RecoveryCase)
        .scalar_subquery()
    )

    stmt = (
        select(RecoveryCase, Customer, subq.label("actual_recovered"))
        .join(Customer, RecoveryCase.customer_id == Customer.customer_id)
        .where(RecoveryCase.status.in_(["OPEN", "IN_PROGRESS"]))
        .order_by(desc(RecoveryCase.expected_net_recovery))
        .limit(limit)
    )

    results = []
    for idx, (case, customer, actual_rec) in enumerate(session.execute(stmt)):
        results.append(
            {
                "priority": idx + 1,
                "case_id": str(case.case_id),
                "customer": f"Cust-{str(customer.customer_id)[:8]}",
                "amount_at_risk": case.amount_at_risk,
                "risk_score": case.risk_score,
                "root_cause": case.root_cause,
                "recommended_action": case.recommended_action,
                "expected_recovery": case.expected_recovery,
                "confidence": case.decision_confidence,
                "status": case.status,
                "expected_net_recovery": case.expected_net_recovery,
                "actual_recovered": actual_rec if actual_rec is not None else Decimal("0.00"),
            }
        )
    return results


def get_all_recovery_cases(session: Session, limit: int = 1000) -> list[dict[str, Any]]:
    """Retrieve all recovery cases regardless of status."""
    from src.database.models import Outcome

    subq = (
        select(func.sum(Outcome.amount_recovered))
        .where(Outcome.case_id == RecoveryCase.case_id)
        .correlate(RecoveryCase)
        .scalar_subquery()
    )

    stmt = (
        select(RecoveryCase, Customer, subq.label("actual_recovered"))
        .join(Customer, RecoveryCase.customer_id == Customer.customer_id)
        .order_by(desc(RecoveryCase.created_at))
        .limit(limit)
    )

    results = []
    for idx, (case, customer, actual_rec) in enumerate(session.execute(stmt)):
        results.append(
            {
                "case_id": str(case.case_id),
                "customer": f"Cust-{str(customer.customer_id)[:8]}",
                "amount_at_risk": case.amount_at_risk,
                "risk_score": case.risk_score,
                "root_cause": case.root_cause,
                "recommended_action": case.recommended_action,
                "expected_recovery": case.expected_recovery,
                "confidence": case.decision_confidence,
                "status": case.status,
                "expected_net_recovery": case.expected_net_recovery,
                "actual_recovered": actual_rec if actual_rec is not None else Decimal("0.00"),
            }
        )
    return results


def get_case_detail(session: Session, case_id: str) -> dict[str, Any] | None:
    """Retrieve full details for a specific case."""
    try:
        case_uuid = uuid.UUID(case_id)
    except ValueError:
        return None

    stmt = select(RecoveryCase, Customer).join(Customer).where(RecoveryCase.case_id == case_uuid)
    row = session.execute(stmt).first()
    if not row:
        return None

    case, customer = row

    # Get the latest intervention
    intervention_stmt = (
        select(Intervention)
        .where(Intervention.case_id == case_uuid)
        .order_by(desc(Intervention.created_at))
        .limit(1)
    )
    intervention = session.scalars(intervention_stmt).first()

    # Get outcome
    from src.database.models import Outcome

    outcome_stmt = (
        select(Outcome)
        .where(Outcome.case_id == case_uuid)
        .order_by(desc(Outcome.created_at))
        .limit(1)
    )
    outcome = session.scalars(outcome_stmt).first()

    # Get the latest audit event to extract candidate actions
    audit_stmt = (
        select(AuditEvent)
        .where(AuditEvent.case_id == case_uuid)
        .order_by(desc(AuditEvent.event_time))
        .limit(1)
    )
    latest_audit = session.scalars(audit_stmt).first()

    candidate_actions = []
    if latest_audit and latest_audit.metadata_:
        candidate_actions = latest_audit.metadata_.get("candidate_actions", [])

    return {
        "case": {
            "id": str(case.case_id),
            "source_type": case.source_type,
            "amount_at_risk": case.amount_at_risk,
            "status": case.status,
            "risk_score": case.risk_score,
            "root_cause": case.root_cause,
            "root_cause_confidence": case.root_cause_confidence,
            "recovery_probability": case.recovery_probability,
            "recommended_action": case.recommended_action,
            "expected_recovery": case.expected_recovery,
            "expected_net_recovery": case.expected_net_recovery,
            "decision_confidence": case.decision_confidence,
            "escalation_required": case.escalation_required,
            "stop_reason": case.stop_reason,
            "created_at": case.created_at,
            "candidate_actions": candidate_actions,
            "amount_recovered": outcome.amount_recovered if outcome else None,
        },
        "customer": {
            "id": str(customer.customer_id),
            "name": f"Customer {str(customer.customer_id)[:8]}",
            "email": f"customer_{str(customer.customer_id)[:8]}@example.com",
            "segment": customer.customer_type,
            "reliability_score": customer.payment_reliability_score,
        },
        "latest_intervention": {
            "action": intervention.action_type,
            "cost": intervention.cost,
            "policy_decision": intervention.policy_decision,
            "policy_reason": intervention.policy_reason,
            "status": intervention.status,
        }
        if intervention
        else None,
    }


def get_decision_trace(session: Session, case_id: str) -> list[dict[str, Any]]:
    """Retrieve chronological audit events for a case."""
    try:
        case_uuid = uuid.UUID(case_id)
    except ValueError:
        return []

    stmt = select(AuditEvent).where(AuditEvent.case_id == case_uuid).order_by(AuditEvent.event_time)
    events = session.scalars(stmt).all()

    return [
        {
            "event_id": str(e.event_id),
            "event_type": e.event_type,
            "event_time": e.event_time,
            "actor": e.actor_type,
            "input_snapshot": e.input_snapshot,
            "decision": e.decision,
            "policy_result": e.policy_result,
            "execution_result": e.execution_result,
            "outcome": e.outcome,
            "metadata": e.metadata_,
        }
        for e in events
    ]


def get_audit_logs(session: Session, limit: int = 100) -> list[dict[str, Any]]:
    """Retrieve recent audit events for the explorer."""
    stmt = select(AuditEvent).order_by(desc(AuditEvent.event_time)).limit(limit)
    events = session.scalars(stmt).all()

    return [
        {
            "event_id": str(e.event_id),
            "case_id": str(e.case_id) if e.case_id else None,
            "event_type": e.event_type,
            "event_time": e.event_time,
            "actor": e.actor_type,
            "correlation_id": e.correlation_id,
            "decision": e.decision,
            "policy_result": e.policy_result,
            "execution_result": e.execution_result,
        }
        for e in events
    ]
