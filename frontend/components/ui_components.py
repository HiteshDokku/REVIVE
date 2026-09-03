"""UI component helpers — delegates to blade_theme for rendering."""

import streamlit as st

from frontend.components.blade_theme import (
    BLUE,
    GREEN,
    RED,
    AMBER,
    GRAY,
    GREEN_BG,
    RED_BG,
    AMBER_BG,
    BLUE_LIGHT,
    GRAY_BG,
    GREEN_BORDER,
    RED_BORDER,
    AMBER_BORDER,
    GRAY_BORDER,
    FONT,
    TEXT,
    TEXT_2,
    TEXT_3,
    SURFACE,
    BORDER,
    RADIUS,
    render_empty_state,
    render_error_state,
    badge_html,
)


def render_kpi_card(title: str, value: str, delta: str | None = None, delta_color: str = "normal"):
    """Render a KPI card (delegates to native st.metric with Blade CSS override)."""
    st.metric(label=title, value=value, delta=delta, delta_color=delta_color)


def get_status_color(status: str) -> str:
    """Map a status string to a hex color."""
    s = status.lower()
    if s in ("recovered", "success", "true", "allow"):
        return GREEN
    if s in ("pending", "in_progress", "escalate"):
        return AMBER
    if s in ("failed", "blocked", "deny", "false"):
        return RED
    if s in ("open", "new"):
        return BLUE
    return GRAY

def format_compact_inr(value: float | str) -> str:
    """Format a large INR value compactly using the Indian numbering system.
    
    Logic:
      - If >= 1,00,00,000 (10M), format as "₹X.XXCr" (Crores)
      - If >= 1,00,000 (100K), format as "₹X.XXL" (Lakhs)
      - If >= 1,000, format as "₹X.XXK" (Thousands)
      - Otherwise, format as "₹X.XX"
    """
    if value is None or value == "":
        return "₹0.00"
    
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("₹", "")
        val = float(value)
    except (ValueError, TypeError):
        return str(value)
        
    abs_val = abs(val)
    sign = "-" if val < 0 else ""
    
    if abs_val >= 10_000_000:
        return f"{sign}₹{abs_val / 10_000_000:.2f}Cr"
    if abs_val >= 100_000:
        return f"{sign}₹{abs_val / 100_000:.2f}L"
    if abs_val >= 1_000:
        return f"{sign}₹{abs_val / 1_000:.2f}K"
    return f"{sign}₹{abs_val:.2f}"


def render_status_badge(status: str):
    """Render a colored pill badge."""
    st.markdown(badge_html(status), unsafe_allow_html=True)
