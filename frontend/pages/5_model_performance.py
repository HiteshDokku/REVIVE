import json
from pathlib import Path

import plotly.express as px
import streamlit as st

from frontend.components.blade_theme import (
    BLUE,
    TEXT,
    FONT,
    inject_blade_css,
    render_blade_header,
    render_section_title,
    render_error_state,
    card_open,
    card_close,
)

st.set_page_config(page_title="Model Performance", page_icon="📈", layout="wide")
inject_blade_css()
render_blade_header("Model Performance", "Evaluation metrics for the M6 Predictive Models (Risk, Root Cause, Recovery).")

_PLOTLY_LAYOUT = dict(
    font=dict(family="Inter, sans-serif", size=13),
    plot_bgcolor="#FFFFFF",
    paper_bgcolor="#FFFFFF",
    title_font=dict(size=14, color=TEXT, family="Inter"),
    margin=dict(l=80, r=20, t=50, b=120),
)


def load_metadata(model_type: str) -> dict | None:
    path = Path(f"artifacts/models/{model_type}_metadata.json")
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return None
    return None


col1, col2, col3 = st.columns(3)

# --- RISK MODEL ---
with col1:
    card_open("Payment Risk Model")
    risk_meta = load_metadata("revenue_risk")
    if not risk_meta:
        render_error_state("Missing Artifact", "revenue_risk_metadata.json not found.")
    else:
        st.write(
            f"**Version:** `{risk_meta.get('model_version', risk_meta.get('version', 'N/A'))}`"
        )
        st.write(f"**Algorithm:** {risk_meta.get('model_type', risk_meta.get('algorithm', 'N/A'))}")

        metrics = risk_meta.get("metrics", {})
        if metrics:
            roc = metrics.get("roc_auc")
            pr = metrics.get("pr_auc")
            brier = metrics.get("brier_score")
            st.metric("ROC AUC", f"{roc:.4f}" if roc is not None else "N/A")
            st.metric("PR AUC", f"{pr:.4f}" if pr is not None else "N/A")
            st.metric("Brier Score", f"{brier:.4f}" if brier is not None else "N/A")

            if "precision" in metrics:
                st.markdown("**Classification Report**")
                prec = metrics.get("precision")
                rec = metrics.get("recall")
                f1 = metrics.get("f1")
                st.write(f"Precision: {prec:.4f}" if prec is not None else "Precision: N/A")
                st.write(f"Recall: {rec:.4f}" if rec is not None else "Recall: N/A")
                st.write(f"F1-Score: {f1:.4f}" if f1 is not None else "F1-Score: N/A")
        else:
            st.info("No evaluation metrics found in metadata.")
    card_close()

# --- ROOT CAUSE MODEL ---
with col2:
    card_open("Root Cause Model")
    rc_meta = load_metadata("root_cause")
    if not rc_meta:
        render_error_state("Missing Artifact", "root_cause_metadata.json not found.")
    else:
        st.write(f"**Version:** `{rc_meta.get('model_version', rc_meta.get('version', 'N/A'))}`")

        st.markdown("**Production Hybrid Pipeline**")
        hy_acc = rc_meta.get("hybrid_accuracy")
        hy_mf1 = rc_meta.get("hybrid_macro_f1")
        det_pct = rc_meta.get("deterministic_resolution_pct")
        ml_pct = rc_meta.get("ml_fallback_pct")

        st.metric("Hybrid Accuracy", f"{hy_acc:.4f}" if hy_acc is not None else "N/A")
        st.metric("Hybrid Macro F1", f"{hy_mf1:.4f}" if hy_mf1 is not None else "N/A")

        if det_pct is not None and ml_pct is not None:
            st.write(f"- **Deterministic:** {det_pct:.1f}%")
            st.write(f"- **ML Fallback:** {ml_pct:.1f}%")

        st.markdown("---")
        st.markdown("**ML Fallback (HistGradientBoosting)**")

        metrics = rc_meta.get("metrics", {})
        if metrics:
            st.write(
                f"**Algorithm:** {metrics.get('model_name', rc_meta.get('model_type', 'N/A'))}"
            )
            acc = metrics.get("accuracy")
            mf1 = metrics.get("macro_f1")
            st.metric("Accuracy", f"{acc:.4f}" if acc is not None else "N/A")
            st.metric("Macro F1", f"{mf1:.4f}" if mf1 is not None else "N/A")

            if "confusion_matrix" in metrics:
                st.session_state["rc_confusion_matrix"] = metrics["confusion_matrix"]
                st.session_state["rc_target_classes"] = rc_meta.get("target_classes")
        else:
            st.info("No evaluation metrics found in metadata.")
    card_close()

# --- RECOVERY MODEL ---
with col3:
    card_open("Recovery Propensity Model")
    rec_meta = load_metadata("recovery_model")
    if not rec_meta:
        render_error_state("Missing Artifact", "recovery_model_metadata.json not found.")
    else:
        st.write(f"**Version:** `{rec_meta.get('model_version', rec_meta.get('version', 'N/A'))}`")
        st.write(f"**Algorithm:** {rec_meta.get('model_type', rec_meta.get('algorithm', 'N/A'))}")

        metrics = rec_meta.get("metrics", {})
        if metrics:
            roc = metrics.get("M6_ROC_AUC", metrics.get("roc_auc"))
            pr = metrics.get("M6_PR_AUC", metrics.get("pr_auc"))
            brier = metrics.get("M6_Brier", metrics.get("brier_score"))
            st.metric("ROC AUC", f"{roc:.4f}" if roc is not None else "N/A")
            st.metric("PR AUC", f"{pr:.4f}" if pr is not None else "N/A")
            st.metric("Brier Score", f"{brier:.4f}" if brier is not None else "N/A")
        else:
            st.info("No evaluation metrics found in metadata.")
    card_close()

st.divider()

cm = st.session_state.get("rc_confusion_matrix")
labels = st.session_state.get("rc_target_classes")

if cm and labels:
    render_section_title("Root Cause — Confusion Matrix")
    fig = px.imshow(
        cm,
        labels=dict(x="Predicted Root Cause", y="Actual Root Cause", color="Count"),
        x=labels,
        y=labels,
        color_continuous_scale="Blues",
        text_auto=True,
        aspect="auto",
    )
    fig.update_layout(**_PLOTLY_LAYOUT, height=700)
    st.plotly_chart(fig, use_container_width=True)

st.info(
    "Calibration charts and deeper visualizations require integration with a dedicated ML tracking server (e.g. MLflow/WandB) which is outside the scope of the offline UI."
)
