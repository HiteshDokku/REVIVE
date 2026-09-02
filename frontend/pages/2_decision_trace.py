import json

import streamlit as st
from frontend.components.ui_components import render_empty_state

from src.api.services.ui_service import get_case_detail, get_decision_trace
from src.database.connection import get_sync_session_factory

st.set_page_config(page_title="Decision Trace", page_icon="🔍", layout="wide")

st.title("Decision Trace")
st.markdown("Explainable timeline of autonomous decisions and actions.")

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

        # Risk
        if etype in ["assess_risk"]:
            if "risk_score" in meta:
                stages["risk"]["score"] = meta["risk_score"]
            if "risk_score" in snap:
                stages["risk"]["score"] = snap["risk_score"]

        # Root cause
        if etype in ["diagnose_root_cause"]:
            if "root_cause" in meta:
                stages["root_cause"]["cause"] = meta["root_cause"]
            if "root_cause_confidence" in meta:
                stages["root_cause"]["confidence"] = meta["root_cause_confidence"]
            if "root_cause" in snap:
                stages["root_cause"]["cause"] = snap["root_cause"]
            if "root_cause_confidence" in snap:
                stages["root_cause"]["confidence"] = snap["root_cause_confidence"]

        # Candidates (options)
        if "recovery_predictions" in meta:
            stages["options"]["candidates"] = meta["recovery_predictions"]
        elif "candidate_actions" in meta and not stages["options"].get("candidates"):
            stages["options"]["candidates"] = meta["candidate_actions"]

        if "recovery_predictions" in snap:
            stages["options"]["candidates"] = snap["recovery_predictions"]
        elif "candidate_actions" in snap and not stages["options"].get("candidates"):
            stages["options"]["candidates"] = snap["candidate_actions"]

        # Selection
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

        # Policy
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

        # Execution
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

        # Outcome
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


def render_timeline_step(title: str, content: str):
    st.markdown(
        f"""
    <div class="timeline-step">
        <div class="timeline-dot"></div>
        <div class="timeline-title">{title}</div>
    """,
        unsafe_allow_html=True,
    )
    st.markdown(content, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


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

        # --- SUMMARY SECTION ---
        st.markdown("### CASE SUMMARY")
        st.markdown("────────────────────────────────────────────")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown("**Amount at Risk**")
            amt = case.get("amount_at_risk", 0)
            st.write(f"₹{float(amt):,.2f}" if amt is not None else "Not available")
            st.markdown("**Risk**")
            risk = case.get("risk_score", 0)
            if risk is not None:
                risk_label = (
                    "HIGH" if float(risk) > 0.7 else "MEDIUM" if float(risk) > 0.4 else "LOW"
                )
                st.write(f"{risk_label} — {float(risk) * 100:.2f}%")
            else:
                st.write("Not available")

        with col2:
            st.markdown("**Root Cause**")
            st.write(f"{case.get('root_cause', 'Not available')}")
            st.markdown("**Selected Action**")
            st.write(f"{case.get('recommended_action', 'Not available')}")

        with col3:
            st.markdown("**Expected Gross Recovery**")
            gross = case.get("expected_recovery", 0)
            st.write(f"₹{float(gross):,.2f}" if gross is not None else "Not available")
            st.markdown("**Expected Net Recovery**")
            net = case.get("expected_net_recovery", 0)
            st.write(f"₹{float(net):,.2f}" if net is not None else "Not available")

        with col4:
            st.markdown("**Case Status**")
            st.write(f"{case.get('status', 'Not available')}")
            st.markdown("**Decision Outcome**")
            st.write(f"{stages['outcome']['status']}")
            st.markdown("**Policy**")
            p_dec = stages["policy"]["decision"]
            if p_dec:
                if p_dec in ["DENY", "DENIED", "BLOCK"]:
                    st.write(f"{p_dec} — {stages['policy']['reason']}")
                else:
                    st.write(f"{p_dec}")
            elif intervention and intervention.get("policy_decision"):
                dec = intervention["policy_decision"]
                if dec in ["DENY", "DENIED", "BLOCK"]:
                    reason = intervention.get("policy_reason", "No reason provided")
                    st.write(f"{dec} — {reason}")
                else:
                    st.write(f"{dec}")
            else:
                st.write("Not evaluated")

        st.divider()

        # --- VISUAL TIMELINE ---
        st.markdown("### HOW REVIVE ARRIVED HERE")

        st.markdown(
            """
        <style>
        .timeline-step { margin-bottom: 2rem; position: relative; padding-left: 25px; border-left: 2px solid #555; }
        .timeline-dot { position: absolute; left: -8px; top: 0; width: 14px; height: 14px; border-radius: 50%; background-color: #4CAF50; }
        .timeline-title { font-size: 1.1em; font-weight: bold; color: #fff; margin-bottom: 10px; }
        .timeline-section { margin-bottom: 8px; font-size: 0.95em; color: #ccc; }
        .timeline-section strong { color: #fff; }
        </style>
        """,
            unsafe_allow_html=True,
        )

        # 1. Payment Failed
        pf_amt = stages["payment_failed"]["amount"]
        pf_str = f"₹{float(pf_amt):,.2f}" if pf_amt is not None else "Not available"
        render_timeline_step(
            "Payment Failed",
            f'<div class="timeline-section">Payment failure detected for {pf_str}</div>',
        )

        # 2. Risk Assessment
        r_score = stages["risk"]["score"]
        if r_score is not None:
            r_pct = f"{float(r_score) * 100:.2f}%"
            r_lab = "HIGH" if float(r_score) > 0.7 else "MEDIUM" if float(r_score) > 0.4 else "LOW"
        else:
            r_pct = "Not available"
            r_lab = "Not available"

        r_html = f"""
        <div class="timeline-section"><strong>What was assessed?</strong><br>Failed payment of {pf_str}</div>
        <div class="timeline-section"><strong>Result</strong><br>Risk = {r_lab}<br>Probability = {r_pct}</div>
        """
        render_timeline_step("🧠 Risk Assessment", r_html)

        # 3. Root Cause Diagnosis
        rc_cause = stages["root_cause"]["cause"] or "Not available"
        rc_conf = stages["root_cause"]["confidence"]
        rc_conf_str = (
            f"Confidence = {float(rc_conf) * 100:.1f}%"
            if rc_conf is not None
            else "Confidence was not recorded for this execution."
        )

        rc_html = f"""
        <div class="timeline-section"><strong>What was being determined?</strong><br>Why did the payment fail?</div>
        <div class="timeline-section"><strong>Result</strong><br>{rc_cause}<br>{rc_conf_str}</div>
        """
        render_timeline_step("🔎 Root Cause Diagnosis", rc_html)

        # 4. Recovery Options
        cands = stages["options"]["candidates"]
        table_html = ""
        if isinstance(cands, list) and len(cands) > 0:
            table_html = (
                "<table border='1' style='width:100%; text-align:left; border-collapse: collapse;'>"
            )
            table_html += "<tr><th>Action</th><th>Recovery Probability</th><th>Cost</th><th>Expected Gross Recovery</th><th>Expected Net Recovery</th><th>Eligible</th></tr>"
            for c in cands:
                if isinstance(c, dict):
                    act = c.get("action_type", c.get("action", "UNKNOWN"))
                    prob = c.get("recovery_probability")
                    prob_str = f"{float(prob) * 100:.1f}%" if prob is not None else "N/A"
                    cost = c.get("action_cost", c.get("cost"))
                    cost_str = f"₹{float(cost):,.2f}" if cost is not None else "N/A"

                    rec_amt = c.get("recoverable_amount", float(pf_amt) if pf_amt else 0.0)
                    gross = (float(prob) * float(rec_amt)) if prob is not None else None
                    gross_str = f"₹{float(gross):,.2f}" if gross is not None else "N/A"

                    net = c.get("expected_net_recovery")
                    if net is None and cost is not None and prob is not None:
                        net = (float(prob) * float(rec_amt)) - float(cost)
                    net_str = f"₹{float(net):,.2f}" if net is not None else "N/A"

                    elig = "✓" if c.get("is_eligible", c.get("eligibility", True)) else "✗"
                    table_html += f"<tr><td><code>{act}</code></td><td>{prob_str}</td><td>{cost_str}</td><td>{gross_str}</td><td>{net_str}</td><td>{elig}</td></tr>"
            table_html += "</table><br>"

        ro_html = f"""
        <div class="timeline-section"><strong>What could REVIVE do?</strong></div>
        <div class="timeline-section">{table_html if table_html else "Candidate action details were not persisted for this execution."}</div>
        """
        render_timeline_step("⚙ Recovery Options", ro_html)

        # 5. Selected Action
        s_act = stages["selection"]["action"] or "Not available"
        s_net = stages["selection"]["expected_net"]
        s_net_str = f"₹{float(s_net):,.2f}" if s_net is not None else "Not available"
        s_conf = stages["selection"]["confidence"]
        s_conf_str = (
            f"Confidence = {float(s_conf) * 100:.1f}%"
            if s_conf is not None
            else "Confidence was not recorded for this execution."
        )
        s_reason = stages["selection"]["reason"]
        if not s_reason:
            if s_act != "Not available":
                s_reason = "Selected action based on policy constraints and net expected value."
            else:
                s_reason = "Selection reason not explicitly recorded."

        sa_html = f"""
        <div class="timeline-section"><strong>REVIVE chose:</strong><br>{s_act}</div>
        <div class="timeline-section"><strong>Details:</strong><br>Expected Net Recovery: {s_net_str}<br>{s_conf_str}</div>
        <div class="timeline-section"><strong>Why?</strong><br>{s_reason}</div>
        """
        render_timeline_step("✓ Selected Action", sa_html)

        # 6. Policy Check
        if not stages["has_policy_event"] and not stages["policy"]["decision"]:
            pc_html = '<div class="timeline-section">Policy decision was not evaluated.</div>'
            p_dec = None
        else:
            p_dec = stages["policy"]["decision"] or "Not available"
            p_reason = stages["policy"]["reason"] or "No specific policy reason provided."
            icon = (
                "✓"
                if p_dec in ["ALLOW", "ALLOWED"]
                else "✕"
                if p_dec in ["DENY", "DENIED", "BLOCK", "DEFAULT_DENY"]
                else "⚠"
            )
            pc_html = f"""
            <div class="timeline-section"><strong>Decision</strong><br>{icon} {p_dec}</div>
            <div class="timeline-section"><strong>Reason</strong><br>{p_reason}</div>
            """
        render_timeline_step("🛡 Policy Check", pc_html)

        # 7. Execution
        if p_dec in ["DENY", "DENIED", "BLOCK", "DEFAULT_DENY"]:
            ex_html = """
            <div class="timeline-section"><strong>🚫 Action Blocked</strong></div>
            <div class="timeline-section">The action was not executed because the policy engine denied it.</div>
            """
        elif not stages["has_execution_event"] and not stages["execution"]["status"]:
            ex_html = '<div class="timeline-section">Action execution has not occurred yet.</div>'
        else:
            e_act = (
                stages["execution"]["action"] or stages["selection"]["action"] or "Unknown Action"
            )
            e_stat = stages["execution"]["status"] or "Not available"
            e_reas = stages["execution"]["reason"]
            icon2 = "✓" if e_stat == "SUCCESS" else "✕" if e_stat in ["FAILED", "BLOCKED"] else "⚠"
            ex_html = f"""
            <div class="timeline-section"><strong>Action</strong><br>{e_act}</div>
            <div class="timeline-section"><strong>Status</strong><br>{icon2} {e_stat}</div>
            """
            if e_reas:
                ex_html += (
                    f'<div class="timeline-section"><strong>Details</strong><br>{e_reas}</div>'
                )
        render_timeline_step("⚡ Action Execution", ex_html)

        # 8. Outcome
        o_rec = stages["outcome"]["recovered"]
        o_rec_str = f"₹{float(o_rec):,.2f}" if o_rec is not None else "₹0.00"
        o_stat = stages["outcome"]["status"]

        ou_html = f"""
        <div class="timeline-section"><strong>Recovered</strong><br>{o_rec_str}</div>
        <div class="timeline-section"><strong>Status</strong><br>{o_stat}</div>
        """
        if o_stat == "PENDING" or o_stat == "STOPPED":
            ou_html += '<div class="timeline-section"><strong>Explanation</strong><br>The selected action has not produced a recorded financial outcome yet.</div>'

        render_timeline_step("💰 Outcome", ou_html)
