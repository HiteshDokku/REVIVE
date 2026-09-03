import json

import streamlit as st

from frontend.components.blade_theme import (
    inject_blade_css,
    render_blade_header,
    render_section_title,
    render_empty_state,
    render_badge,
    badge_html,
    render_timeline_step,
    html_table,
    card_open,
    card_close,
    kv,
    kv_code,
)
from src.api.services.ui_service import get_case_detail, get_decision_trace
from src.database.connection import get_sync_session_factory

st.set_page_config(page_title="Decision Trace", page_icon="🔍", layout="wide")
inject_blade_css()
render_blade_header("Decision Trace", "Explainable timeline of autonomous decisions and actions.")

case_id_input = st.text_input(
    "Enter Case ID (UUID):", placeholder="e.g. 123e4567-e89b-12d3-a456-426614174000"
)


def safe_dict(val) -> dict:
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return val if isinstance(val, dict) else {}


def build_logical_trace(events, case, intervention):
    stages = {}

    # Defaults from case
    stages["payment_failed"] = {"amount": case.get("amount_at_risk")}
    stages["risk"] = {"score": case.get("risk_score")}
    stages["root_cause"] = {
        "cause": case.get("root_cause"),
        "confidence": case.get("root_cause_confidence"),
}
    stages["options"] = {"candidates": case.get("candidate_actions", [])}
    stages["selection"] = {
        "action": case.get("recommended_action"),
        "expected_net": case.get("expected_net_recovery"),
        "confidence": case.get("decision_confidence"),
        "reason": None,
}
    stages["policy"] = {
        "decision": intervention.get("policy_decision") if intervention else None,
        "reason": intervention.get("policy_reason") if intervention else None,
}
    stages["execution"] = {
        "action": intervention.get("action") if intervention else None,
        "status": intervention.get("status") if intervention else None,
        "reason": None,
}
    stages["outcome"] = {
        "recovered": case.get("amount_recovered") or 0.0,
        "status": case.get("status", "PENDING"),
}

    has_policy_event = False
    has_execution_event = False
    has_outcome_event = False

    for e in events:
        etype = e.get("event_type")
        meta = safe_dict(e.get("metadata"))
        snap = safe_dict(e.get("input_snapshot"))

        if etype in ["assess_risk"]:
            if "risk_score" in meta:
                stages["risk"]["score"] = meta["risk_score"]
            if "risk_score" in snap:
                stages["risk"]["score"] = snap["risk_score"]

        if etype in ["diagnose_root_cause"]:
            if "root_cause" in meta:
                stages["root_cause"]["cause"] = meta["root_cause"]
            if "root_cause_confidence" in meta:
                stages["root_cause"]["confidence"] = meta["root_cause_confidence"]
            if "root_cause" in snap:
                stages["root_cause"]["cause"] = snap["root_cause"]
            if "root_cause_confidence" in snap:
                stages["root_cause"]["confidence"] = snap["root_cause_confidence"]

        if "recovery_predictions" in meta:
            stages["options"]["candidates"] = meta["recovery_predictions"]
        elif "candidate_actions" in meta and not stages["options"].get("candidates"):
            stages["options"]["candidates"] = meta["candidate_actions"]

        if "recovery_predictions" in snap:
            stages["options"]["candidates"] = snap["recovery_predictions"]
        elif "candidate_actions" in snap and not stages["options"].get("candidates"):
            stages["options"]["candidates"] = snap["candidate_actions"]

        if etype in ["optimize_action", "generate_candidate_actions"]:
            dec = e.get("decision")
            if isinstance(dec, str):
                if dec.startswith("{"):
                    d_dict = safe_dict(dec)
                    stages["selection"]["action"] = d_dict.get(
                        "selected_action", d_dict.get("action", dec)
                    )
                elif dec != "null":
                    stages["selection"]["action"] = dec
            elif isinstance(dec, dict):
                stages["selection"]["action"] = dec.get("selected_action", dec.get("action"))

            if "selected_action" in meta:
                stages["selection"]["action"] = meta["selected_action"]
            if "expected_net_recovery" in meta:
                stages["selection"]["expected_net"] = meta["expected_net_recovery"]
            if "reason" in meta:
                stages["selection"]["reason"] = meta["reason"]

        if etype in ["policy_check"]:
            has_policy_event = True
            pr = safe_dict(e.get("policy_result"))
            if "policy_decision" in meta:
                stages["policy"]["decision"] = meta["policy_decision"]
            if "violated_guardrails" in meta:
                stages["policy"]["reason"] = "Violated guardrails: " + ", ".join(
                    meta["violated_guardrails"]
                )
            if "decision" in pr:
                stages["policy"]["decision"] = pr["decision"]
            if "reason" in pr:
                stages["policy"]["reason"] = pr["reason"]

        if etype in ["execute_action", "execution"]:
            has_execution_event = True
            er = safe_dict(e.get("execution_result"))
            if "status" in meta:
                stages["execution"]["status"] = meta["status"]
            if "action" in meta:
                stages["execution"]["action"] = meta["action"]
            if "status" in er:
                stages["execution"]["status"] = er["status"]
            if "action" in er:
                stages["execution"]["action"] = er["action"]
            if "reason" in er:
                stages["execution"]["reason"] = er["reason"]

        if etype in ["record_outcome", "outcome_observation", "stop_case"]:
            if etype != "stop_case":
                has_outcome_event = True
            out = safe_dict(e.get("outcome"))
            if "amount_recovered" in meta:
                stages["outcome"]["recovered"] = meta["amount_recovered"]
            if "status" in meta:
                stages["outcome"]["status"] = meta["status"]
            if "amount_recovered" in out:
                stages["outcome"]["recovered"] = out["amount_recovered"]
            if "status" in out:
                stages["outcome"]["status"] = out["status"]

    stages["has_policy_event"] = has_policy_event
    stages["has_execution_event"] = has_execution_event
    stages["has_outcome_event"] = has_outcome_event

    return stages


if case_id_input:
    SessionLocal = get_sync_session_factory()
    with SessionLocal() as session:
        events = get_decision_trace(session, case_id_input)
        case_details = get_case_detail(session, case_id_input)

    if not events or not case_details:
        render_empty_state(
            f"No trace found for Case ID: {case_id_input}. Check the ID and try again."
        )
    else:
        case = case_details["case"]
        intervention = case_details["latest_intervention"]
        stages = build_logical_trace(events, case, intervention)

        # ── CASE SUMMARY CARD ─────────────────────────────────────────────
        card_open("Case Summary")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            amt = case.get("amount_at_risk", 0)
            st.markdown(kv("Amount at Risk", f"₹{float(amt):,.2f}" if amt else "N/A"), unsafe_allow_html=True)
            risk = case.get("risk_score", 0)
            if risk is not None:
                rl = "HIGH" if float(risk) > 0.7 else "MEDIUM" if float(risk) > 0.4 else "LOW"
                st.markdown(kv("Risk", f"{rl} — {float(risk)*100:.1f}%"), unsafe_allow_html=True)
        with col2:
            st.markdown(
                kv("Root Cause", case.get("root_cause", "N/A"))
                + kv("Selected Action", case.get("recommended_action", "N/A")),
                unsafe_allow_html=True,
            )
        with col3:
            gross = case.get("expected_recovery", 0)
            net = case.get("expected_net_recovery", 0)
            st.markdown(
                kv("Gross Recovery", f"₹{float(gross):,.2f}" if gross else "N/A")
                + kv("Net Recovery", f"₹{float(net):,.2f}" if net else "N/A"),
                unsafe_allow_html=True,
            )
        with col4:
            st.write("**Status**")
            render_badge(case.get("status", "UNKNOWN"))
            st.write("**Policy**")
            p_dec = stages["policy"]["decision"]
            if p_dec:
                render_badge(p_dec)
                if p_dec in ("DENY", "DENIED", "BLOCK"):
                    st.caption(stages["policy"]["reason"] or "")
            elif intervention and intervention.get("policy_decision"):
                dec = intervention["policy_decision"]
                render_badge(dec)
                if dec in ("DENY", "DENIED", "BLOCK"):
                    st.caption(intervention.get("policy_reason", ""))
            else:
                st.write("Not evaluated")
        card_close()

        st.divider()

        # ── TIMELINE STEPPER ──────────────────────────────────────────────
        render_section_title("How REVIVE Arrived Here")

        pf_amt = stages["payment_failed"]["amount"]
        pf_str = f"₹{float(pf_amt):,.2f}" if pf_amt is not None else "N/A"

        # 1. Payment Failed
        render_timeline_step(1, "Payment Failed",
            f"Payment failure detected for <strong>{pf_str}</strong>",
            status="danger")

        # 2. Risk Assessment
        r_score = stages["risk"]["score"]
        if r_score is not None:
            r_pct = f"{float(r_score)*100:.1f}%"
            r_lab = "HIGH" if float(r_score) > 0.7 else "MEDIUM" if float(r_score) > 0.4 else "LOW"
        else:
            r_pct = "N/A"
            r_lab = "N/A"
        render_timeline_step(2, "Risk Assessment",
            f"<strong>Assessment:</strong> Failed payment of {pf_str}<br>"
            f"<strong>Result:</strong> Risk = {r_lab} · Probability = {r_pct}",
            status="primary")

        # 3. Root Cause
        rc_cause = stages["root_cause"]["cause"] or "N/A"
        rc_conf = stages["root_cause"]["confidence"]
        rc_conf_s = f"{float(rc_conf)*100:.1f}%" if rc_conf is not None else "Not recorded"
        render_timeline_step(3, "Root Cause Diagnosis",
            f"<strong>Question:</strong> Why did the payment fail?<br>"
            f"<strong>Result:</strong> {rc_cause} · Confidence = {rc_conf_s}",
            status="primary")

        # 4. Recovery Options
        cands = stages["options"]["candidates"]
        if isinstance(cands, list) and len(cands) > 0:
            headers = ["Action", "Recovery Prob.", "Cost", "Gross", "Net", "Eligible"]
            rows = []
            for ci in cands:
                if isinstance(ci, dict):
                    act = ci.get("action_type", ci.get("action", "?"))
                    prob = ci.get("recovery_probability")
                    ps = f"{float(prob)*100:.1f}%" if prob is not None else "N/A"
                    cost = ci.get("action_cost", ci.get("cost"))
                    cs = f"₹{float(cost):,.2f}" if cost is not None else "N/A"
                    rec = ci.get("recoverable_amount", float(pf_amt) if pf_amt else 0)
                    gv = float(prob)*float(rec) if prob is not None else None
                    gs = f"₹{gv:,.2f}" if gv is not None else "N/A"
                    nv = ci.get("expected_net_recovery")
                    if nv is None and cost is not None and prob is not None:
                        nv = float(prob)*float(rec) - float(cost)
                    ns = f"₹{float(nv):,.2f}" if nv is not None else "N/A"
                    el = "✓" if ci.get("is_eligible", ci.get("eligibility", True)) else "✗"
                    rows.append([f"<code>{act}</code>", ps, cs, gs, ns, el])
            tbl = html_table(headers, rows)
            render_timeline_step(4, "Recovery Options",
                f"<strong>What could REVIVE do?</strong><br><br>{tbl}",
                status="primary")
        else:
            render_timeline_step(4, "Recovery Options",
                "Candidate action details were not persisted for this execution.",
                status="neutral")

        # 5. Selected Action
        s_act = stages["selection"]["action"] or "N/A"
        s_net = stages["selection"]["expected_net"]
        s_net_s = f"₹{float(s_net):,.2f}" if s_net is not None else "N/A"
        s_conf = stages["selection"]["confidence"]
        s_conf_s = f"{float(s_conf)*100:.1f}%" if s_conf is not None else "Not recorded"
        s_reason = stages["selection"]["reason"]
        if not s_reason:
            s_reason = "Selected based on policy constraints and net expected value." if s_act != "N/A" else "Not recorded."
        render_timeline_step(5, "Selected Action",
            f"<strong>REVIVE chose:</strong> {s_act}<br>"
            f"<strong>Net Recovery:</strong> {s_net_s} · Confidence = {s_conf_s}<br>"
            f"<strong>Why:</strong> {s_reason}",
            status="success")

        # 6. Policy Check
        if not stages["has_policy_event"] and not stages["policy"]["decision"]:
            pc_html = "Policy decision was not evaluated."
            p_dec_val = None
            pc_status = "neutral"
        else:
            p_dec_val = stages["policy"]["decision"] or "N/A"
            p_reason = stages["policy"]["reason"] or "No specific reason provided."
            if p_dec_val in ("ALLOW", "ALLOWED"):
                pc_status = "success"
                ic = "✓"
            elif p_dec_val in ("DENY", "DENIED", "BLOCK", "DEFAULT_DENY"):
                pc_status = "danger"
                ic = "✕"
            else:
                pc_status = "warning"
                ic = "⚠"
            pc_html = (
                f"<strong>Decision:</strong> {ic} {p_dec_val} {badge_html(p_dec_val)}<br>"
                f"<strong>Reason:</strong> {p_reason}"
            )
        render_timeline_step(6, "Policy Check", pc_html, status=pc_status)

        # 7. Execution
        if p_dec_val in ("DENY", "DENIED", "BLOCK", "DEFAULT_DENY"):
            ex_html = "<strong>🚫 Action Blocked</strong><br>Policy engine denied execution."
            ex_status = "danger"
        elif not stages["has_execution_event"] and not stages["execution"]["status"]:
            ex_html = "Action execution has not occurred yet."
            ex_status = "neutral"
        else:
            e_act = stages["execution"]["action"] or stages["selection"]["action"] or "Unknown"
            e_stat = stages["execution"]["status"] or "N/A"
            e_reas = stages["execution"]["reason"]
            if e_stat == "SUCCESS":
                ex_status = "success"
                ic2 = "✓"
            elif e_stat in ("FAILED", "BLOCKED"):
                ex_status = "danger"
                ic2 = "✕"
            else:
                ex_status = "warning"
                ic2 = "⚠"
            ex_html = f"<strong>Action:</strong> {e_act}<br><strong>Status:</strong> {ic2} {e_stat} {badge_html(e_stat)}"
            if e_reas:
                ex_html += f"<br><strong>Details:</strong> {e_reas}"
        render_timeline_step(7, "Action Execution", ex_html, status=ex_status)

        # 8. Outcome
        o_rec = stages["outcome"]["recovered"]
        o_rec_s = f"₹{float(o_rec):,.2f}" if o_rec is not None else "₹0.00"
        o_stat = stages["outcome"]["status"]

        if o_stat in ("RECOVERED", "CLOSED"):
            ou_status = "success"
        elif o_stat in ("FAILED",):
            ou_status = "danger"
        elif o_stat in ("PENDING", "STOPPED"):
            ou_status = "warning"
        else:
            ou_status = "neutral"

        ou_html = (
            f"<strong>Recovered:</strong> {o_rec_s}<br>"
            f"<strong>Status:</strong> {badge_html(o_stat)}"
        )
        if o_stat in ("PENDING", "STOPPED"):
            ou_html += "<br><strong>Explanation:</strong> No recorded financial outcome yet."

        render_timeline_step(8, "Outcome", ou_html, status=ou_status, is_last=True)
