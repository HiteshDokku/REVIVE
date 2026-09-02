import streamlit as st


def render_kpi_card(title: str, value: str, delta: str | None = None, delta_color: str = "normal"):
    """Render a KPI card."""
    st.metric(label=title, value=value, delta=delta, delta_color=delta_color)


def get_status_color(status: str) -> str:
    """Map a status string to a visual color mapping."""
    status_lower = status.lower()
    if status_lower in ["recovered", "success", "true", "allow"]:
        return "green"
    if status_lower in ["pending", "in_progress", "escalate"]:
        return "orange"
    if status_lower in ["failed", "blocked", "deny", "false"]:
        return "red"
    if status_lower in ["open", "new"]:
        return "blue"
    return "gray"


def render_status_badge(status: str):
    """Render a colored status badge."""
    color = get_status_color(status)
    st.markdown(
        f"<span style='padding: 0.2rem 0.6rem; border-radius: 4px; color: white; background-color: {color}; font-size: 0.85em; font-weight: bold;'>{status.upper()}</span>",
        unsafe_allow_html=True,
    )


def render_empty_state(message: str):
    """Render a standard empty state message."""
    st.info(f"📭 {message}")


def render_error_state(title: str, message: str, correlation_id: str | None = None):
    """Render a standard error state."""
    st.error(f"**{title}**\n\n{message}")
    if correlation_id:
        st.caption(f"Correlation ID: {correlation_id}")
