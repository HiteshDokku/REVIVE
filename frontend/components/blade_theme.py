"""Razorpay Blade Design System — Complete Streamlit UI Override.

This module injects aggressive CSS that hides all default Streamlit
chrome (header, footer, hamburger, padding) and replaces it with a
fully custom SaaS-grade dashboard shell.

All helpers produce raw HTML consumed via st.markdown(unsafe_allow_html=True).
No business logic or data imports live here.
"""

from __future__ import annotations

import streamlit as st

# ─── Design Tokens ────────────────────────────────────────────────────────
BLUE = "#0000EE"
BLUE_HOVER = "#0000CC"
BLUE_LIGHT = "#EEF2FF"
BLUE_50 = "#F0F0FF"

BG = "#F6F7F9"
SURFACE = "#FFFFFF"
BORDER = "#E2E4E9"
BORDER_LIGHT = "#F0F1F3"

TEXT = "#1B1F2E"
TEXT_2 = "#5E6278"
TEXT_3 = "#9EA2B0"

GREEN = "#12B76A"
GREEN_BG = "#ECFDF3"
GREEN_BORDER = "#A6F4C5"

RED = "#F04438"
RED_BG = "#FEF3F2"
RED_BORDER = "#FECDCA"

AMBER = "#F79009"
AMBER_BG = "#FFFAEB"
AMBER_BORDER = "#FEDF89"

GRAY = "#667085"
GRAY_BG = "#F2F4F7"
GRAY_BORDER = "#D0D5DD"

SHADOW_SM = "0 1px 2px rgba(0,0,0,0.05)"
SHADOW_MD = "0 2px 8px rgba(0,0,0,0.08)"
SHADOW_LG = "0 4px 16px rgba(0,0,0,0.10)"
SHADOW_BLUE = "0 4px 14px rgba(0,0,238,0.12)"

FONT = "'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif"
RADIUS = "10px"
RADIUS_SM = "6px"
RADIUS_XS = "4px"

# ─── Master CSS ───────────────────────────────────────────────────────────
_CSS = f"""
<style>
/* ═══════════════════════════════════════════════════════════════════════
   GOOGLE FONTS
   ═══════════════════════════════════════════════════════════════════════ */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

/* ═══════════════════════════════════════════════════════════════════════
   HIDE ALL DEFAULT STREAMLIT CHROME
   ═══════════════════════════════════════════════════════════════════════ */
#MainMenu {{visibility:hidden !important;}}
header[data-testid="stHeader"] {{display:none !important;}}
footer {{display:none !important;}}
.stDeployButton {{display:none !important;}}
div[data-testid="stToolbar"] {{display:none !important;}}
div[data-testid="stDecoration"] {{display:none !important;}}
div[data-testid="stStatusWidget"] {{display:none !important;}}

/* Remove default top padding so content starts flush */
.stApp > div:first-child {{
    padding-top: 0 !important;
}}
.block-container {{
    padding-top: 2rem !important;
    padding-bottom: 2rem !important;
    max-width: 1400px !important;
}}

/* ═══════════════════════════════════════════════════════════════════════
   GLOBAL TYPOGRAPHY
   ═══════════════════════════════════════════════════════════════════════ */
html, body, [class*="css"], .stApp {{
    font-family: {FONT} !important;
-webkit-font-smoothing: antialiased !important;
-moz-osx-font-smoothing: grayscale !important;
}}
.stApp {{
    background: {BG} !important;
}}
h1,h2,h3,h4,h5,h6 {{
    font-family: {FONT} !important;
    color: {TEXT} !important;
    letter-spacing: -0.025em !important;
}}
p, li, td, th, label {{
    font-family: {FONT} !important;
}}

/* ═══════════════════════════════════════════════════════════════════════
   FIX STREAMLIT ICONS & METRICS
   ═══════════════════════════════════════════════════════════════════════ */
.material-symbols-rounded, .material-icons, [class*="stIcon"] {{
    font-family: "Material Symbols Rounded", "Material Icons" !important;
}}
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"],
.stSidebarCollapseButton {{
    display: none !important; /* Hide sidebar collapse button */
    opacity: 0 !important;
    width: 0 !important;
    font-size: 0 !important;
}}
[data-testid="stMetric"] {{
    overflow: hidden !important;
    min-width: 0 !important;
}}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * {{
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    font-size: 1.25rem !important;
    letter-spacing: -0.02em !important;
}}
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {{
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    font-size: 0.75rem !important;
    letter-spacing: 0 !important;
}}

/* Rename 'app' to 'Home' in sidebar nav */
[data-testid="stSidebarNav"] ul li:first-child a span {{
    visibility: hidden;
    position: relative;
}}
[data-testid="stSidebarNav"] ul li:first-child a span::after {{
    content: "Home";
    visibility: visible;
    position: absolute;
    left: 0;
    top: 0;
}}

/* ═══════════════════════════════════════════════════════════════════════
   SIDEBAR — Dark navy theme matching Razorpay dashboard
   ═══════════════════════════════════════════════════════════════════════ */
section[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #0C1021 0%, #141B2D 100%) !important;
    border-right: none !important;
    box-shadow: 2px 0 12px rgba(0,0,0,0.15) !important;
}}
section[data-testid="stSidebar"] * {{
    color: #C8CEDE !important;
}}
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] .stMarkdown span,
section[data-testid="stSidebar"] .stMarkdown li {{
    color: #C8CEDE !important;
    font-size: 0.88rem !important;
}}
section[data-testid="stSidebar"] .stMarkdown h1,
section[data-testid="stSidebar"] .stMarkdown h2,
section[data-testid="stSidebar"] .stMarkdown h3 {{
    color: #FFFFFF !important;
}}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"]::before {{
    content: "RazorPay Buildathon\\A Revive";
    white-space: pre-wrap;
    display: block;
    padding: 1.5rem 1.5rem 1rem 1.5rem;
    font-family: {FONT} !important;
    font-size: 1.2rem;
    font-weight: 800;
    color: #FFFFFF;
    line-height: 1.4;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    margin-bottom: 1rem;
}}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a {{
    color: #9BA3B5 !important;
    border-radius: 8px !important;
    margin: 2px 8px !important;
    padding: 8px 12px !important;
    transition: all 0.15s ease !important;
    font-weight: 500 !important;
    font-size: 0.88rem !important;
}}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover {{
    background: rgba(255,255,255,0.06) !important;
    color: #FFFFFF !important;
}}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] {{
    background: rgba(0,0,238,0.15) !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
    border-left: 3px solid {BLUE} !important;
}}

/* ═══════════════════════════════════════════════════════════════════════
   BUTTONS
   ═══════════════════════════════════════════════════════════════════════ */
.stButton > button {{
    font-family: {FONT} !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    border-radius: 8px !important;
    border: 1px solid {BORDER} !important;
    background: {SURFACE} !important;
    color: {TEXT} !important;
    padding: 0.5rem 1rem !important;
    transition: all 0.15s ease !important;
    box-shadow: {SHADOW_SM} !important;
}}
.stButton > button:hover {{
    border-color: {BLUE} !important;
    color: {BLUE} !important;
    box-shadow: {SHADOW_BLUE} !important;
    transform: translateY(-1px) !important;
}}
.stButton > button:active {{
    transform: translateY(0) !important;
}}
/* Primary button */
.stButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"] {{
    background: {BLUE} !important;
    color: #FFF !important;
    border: none !important;
    box-shadow: 0 2px 8px rgba(0,0,238,0.25) !important;
}}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="stBaseButton-primary"]:hover {{
    background: {BLUE_HOVER} !important;
    box-shadow: 0 4px 14px rgba(0,0,238,0.30) !important;
}}

/* ═══════════════════════════════════════════════════════════════════════
   INPUTS & CONTROLS
   ═══════════════════════════════════════════════════════════════════════ */
.stTextInput input,
.stNumberInput input {{
    border-radius: 8px !important;
    border: 1px solid {BORDER} !important;
    font-family: {FONT} !important;
    font-size: 0.88rem !important;
    padding: 0.6rem 0.75rem !important;
    background: {SURFACE} !important;
    transition: all 0.15s ease !important;
    box-shadow: {SHADOW_SM} !important;
}}
.stTextInput input:focus,
.stNumberInput input:focus {{
    border-color: {BLUE} !important;
    box-shadow: 0 0 0 3px rgba(0,0,238,0.10) !important;
    outline: none !important;
}}
.stSelectbox > div > div,
.stMultiSelect > div {{
    border-radius: 8px !important;
    border-color: {BORDER} !important;
}}
/* Label styling */
.stTextInput label, .stSelectbox label, .stMultiSelect label, .stNumberInput label {{
    font-family: {FONT} !important;
    font-weight: 600 !important;
    font-size: 0.8rem !important;
    color: {TEXT_2} !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
}}

/* ═══════════════════════════════════════════════════════════════════════
   EXPANDER
   ═══════════════════════════════════════════════════════════════════════ */
details[data-testid="stExpander"] {{
    background: {SURFACE} !important;
    border: 1px solid {BORDER} !important;
    border-radius: {RADIUS} !important;
    box-shadow: {SHADOW_SM} !important;
    overflow: hidden !important;
}}
details[data-testid="stExpander"] summary {{
    font-family: {FONT} !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    color: {TEXT} !important;
    padding: 1rem 1.25rem !important;
}}

/* ═══════════════════════════════════════════════════════════════════════
   METRICS (native st.metric override)
   ═══════════════════════════════════════════════════════════════════════ */
[data-testid="stMetric"] {{
    background: {SURFACE} !important;
    border: 1px solid {BORDER} !important;
    border-radius: {RADIUS} !important;
    padding: 1.25rem !important;
    box-shadow: {SHADOW_SM} !important;
    transition: all 0.2s cubic-bezier(0.4,0,0.2,1) !important;
}}
[data-testid="stMetric"]:hover {{
    box-shadow: {SHADOW_BLUE} !important;
    border-color: {BLUE} !important;
    transform: translateY(-2px) !important;
}}
[data-testid="stMetricLabel"] {{
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
    color: {TEXT_2} !important;
    white-space: normal !important;
    word-break: break-word !important;
}}
[data-testid="stMetricValue"] {{
    font-weight: 800 !important;
    color: {TEXT} !important;
    white-space: normal !important;
    word-break: break-word !important;
}}
[data-testid="stMetricDelta"] {{
    font-weight: 600 !important;
    white-space: normal !important;
    word-break: break-word !important;
}}

/* ═══════════════════════════════════════════════════════════════════════
   DATA FRAMES
   ═══════════════════════════════════════════════════════════════════════ */
[data-testid="stDataFrame"] {{
    border: 1px solid {BORDER} !important;
    border-radius: {RADIUS} !important;
    overflow: hidden !important;
    box-shadow: {SHADOW_SM} !important;
}}

/* ═══════════════════════════════════════════════════════════════════════
   PLOTLY CHARTS
   ═══════════════════════════════════════════════════════════════════════ */
[data-testid="stPlotlyChart"] {{
    background: {SURFACE} !important;
    border: 1px solid {BORDER} !important;
    border-radius: {RADIUS} !important;
    padding: 8px !important;
    box-shadow: {SHADOW_SM} !important;
}}

/* ═══════════════════════════════════════════════════════════════════════
   ALERTS (info/success/error/warning)
   ═══════════════════════════════════════════════════════════════════════ */
div[data-testid="stAlert"] > div {{
    border-radius: 8px !important;
    font-size: 0.88rem !important;
    font-family: {FONT} !important;
}}

/* ═══════════════════════════════════════════════════════════════════════
   DIVIDERS
   ═══════════════════════════════════════════════════════════════════════ */
hr {{
    border: none !important;
    border-top: 1px solid {BORDER_LIGHT} !important;
    margin: 1.5rem 0 !important;
}}

/* ═══════════════════════════════════════════════════════════════════════
   TABS
   ═══════════════════════════════════════════════════════════════════════ */
.stTabs [data-baseweb="tab-list"] {{
    gap: 0 !important;
    background: transparent !important;
    border-bottom: 2px solid {BORDER_LIGHT} !important;
}}
.stTabs [data-baseweb="tab"] {{
    font-family: {FONT} !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    color: {TEXT_3} !important;
    padding: 0.75rem 1.25rem !important;
    border-bottom: 2px solid transparent !important;
    transition: all 0.15s ease !important;
}}
.stTabs [aria-selected="true"] {{
    color: {BLUE} !important;
    border-bottom-color: {BLUE} !important;
}}

/* ═══════════════════════════════════════════════════════════════════════
   SPINNER
   ═══════════════════════════════════════════════════════════════════════ */
.stSpinner > div {{
    border-top-color: {BLUE} !important;
}}

/* ═══════════════════════════════════════════════════════════════════════
   SKELETON / PULSE ANIMATION
   ═══════════════════════════════════════════════════════════════════════ */
@keyframes rv-pulse {{
  0%,100% {{ opacity:1; }}
  50% {{ opacity:0.4; }}
}}
.rv-skeleton {{
    background: linear-gradient(90deg,{GRAY_BG} 0%,#E8E9ED 50%,{GRAY_BG} 100%);
    background-size: 200% 100%;
    animation: rv-pulse 1.8s ease-in-out infinite;
    border-radius: 6px;
}}

</style>
"""


# ─── Injection ────────────────────────────────────────────────────────────

def inject_blade_css() -> None:
    """Inject full Blade design system CSS. Call once per page after set_page_config."""
    st.markdown(_CSS, unsafe_allow_html=True)
    
    # Global sidebar branding for all pages
    with st.sidebar:
        st.markdown(f"""
<div style="padding:20px 4px 24px;border-bottom:1px solid rgba(255,255,255,0.08);margin-bottom:12px;">
<div style="display:flex;align-items:center;gap:10px;">
<div style="width:32px;height:32px;border-radius:8px;background:linear-gradient(135deg,{BLUE},#4F46E5);
                display:flex;align-items:center;justify-content:center;box-shadow:0 2px 8px rgba(0,0,238,0.3);">
<span style="color:#FFF;font-weight:900;font-size:0.85rem;">R</span>
</div>
<div>
<div style="font-weight:800;font-size:0.95rem;color:#FFF;letter-spacing:-0.02em;">RazorPay Buildathon</div>
<div style="font-size:0.68rem;color:#7B8399;font-weight:500;text-transform:uppercase;letter-spacing:0.04em;">REVIVE</div>
</div>
</div>
</div>
        """, unsafe_allow_html=True)



# ─── Page Header ──────────────────────────────────────────────────────────

def render_blade_header(title: str, subtitle: str = "") -> None:
    """Branded page header with logo mark and gradient accent."""
    sub = f'<p style="margin:4px 0 0;font-size:0.92rem;color:{TEXT_2};font-weight:400;">{subtitle}</p>' if subtitle else ""
    st.markdown(f"""
<div style="margin-bottom:28px;">
<div style="display:flex;align-items:center;gap:12px;">
<div style="width:40px;height:40px;border-radius:10px;background:linear-gradient(135deg,{BLUE},#4F46E5);
                display:flex;align-items:center;justify-content:center;box-shadow:0 2px 8px rgba(0,0,238,0.25);">
<span style="color:#FFF;font-weight:900;font-size:1.1rem;font-family:{FONT};">R</span>
</div>
<div>
<h1 style="margin:0;padding:0;font-size:1.65rem;font-weight:800;color:{TEXT};
                    letter-spacing:-0.03em;line-height:1.2;">{title}</h1>
{sub}
</div>
</div>
</div>
    """, unsafe_allow_html=True)


# ─── Section Title ────────────────────────────────────────────────────────

def render_section_title(title: str, subtitle: str = "") -> None:
    """Render a section heading with optional subtitle."""
    sub = f'<span style="font-weight:400;color:{TEXT_3};font-size:0.82rem;margin-left:8px;">{subtitle}</span>' if subtitle else ""
    st.markdown(f"""
<div style="margin:24px 0 16px;display:flex;align-items:baseline;gap:4px;">
<span style="font-family:{FONT};font-size:0.72rem;font-weight:700;color:{TEXT_2};
            text-transform:uppercase;letter-spacing:0.08em;">{title}</span>
{sub}
</div>
    """, unsafe_allow_html=True)


# ─── KPI Card ─────────────────────────────────────────────────────────────

def render_kpi_row(kpis: list[dict]) -> None:
    """Render a row of KPI metric cards.

    Each dict: {label, value, icon?, sublabel?}
    """
    cards = ""
    for k in kpis:
        icon = k.get("icon", "")
        sublabel = ""
        if k.get("sublabel"):
            sublabel = f'<div style="font-size:0.75rem;color:{TEXT_3};margin-top:4px;">{k["sublabel"]}</div>'
        cards += f"""
<div style="flex:1 1 0;min-width:0;background:{SURFACE};border:1px solid {BORDER};
            border-radius:{RADIUS};padding:16px 12px;box-shadow:{SHADOW_SM};
            transition:all 0.2s cubic-bezier(0.4,0,0.2,1);cursor:default;position:relative;overflow:hidden;"
            onmouseenter="this.style.boxShadow='{SHADOW_BLUE}';this.style.borderColor='{BLUE}';this.style.transform='translateY(-2px)';"
            onmouseleave="this.style.boxShadow='{SHADOW_SM}';this.style.borderColor='{BORDER}';this.style.transform='none';">
<div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;
                color:{TEXT_2};margin-bottom:8px;display:flex;align-items:center;gap:6px;white-space:nowrap !important;overflow:hidden !important;text-overflow:ellipsis !important;">
{f'<span style="font-size:1rem;">{icon}</span>' if icon else ""}{k['label']}
</div>
<div style="font-size:1.25rem;font-weight:800;color:{TEXT};line-height:1.2;letter-spacing:-0.02em;white-space:nowrap !important;overflow:hidden !important;text-overflow:ellipsis !important;">
{k['value']}
</div>
{sublabel}
</div>"""
    st.markdown(f"""
<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px;">
{cards}
</div>
    """, unsafe_allow_html=True)


# ─── Badge ────────────────────────────────────────────────────────────────

_BADGE_MAP = {
    "allow": (GREEN, GREEN_BG, GREEN_BORDER),
    "allowed": (GREEN, GREEN_BG, GREEN_BORDER),
    "success": (GREEN, GREEN_BG, GREEN_BORDER),
    "recovered": (GREEN, GREEN_BG, GREEN_BORDER),
    "true": (GREEN, GREEN_BG, GREEN_BORDER),
    "pass": (GREEN, GREEN_BG, GREEN_BORDER),
    "deny": (RED, RED_BG, RED_BORDER),
    "denied": (RED, RED_BG, RED_BORDER),
    "block": (RED, RED_BG, RED_BORDER),
    "blocked": (RED, RED_BG, RED_BORDER),
    "default_deny": (RED, RED_BG, RED_BORDER),
    "failed": (RED, RED_BG, RED_BORDER),
    "false": (RED, RED_BG, RED_BORDER),
    "fail": (RED, RED_BG, RED_BORDER),
    "pending": (AMBER, AMBER_BG, AMBER_BORDER),
    "in_progress": (AMBER, AMBER_BG, AMBER_BORDER),
    "escalate": (AMBER, AMBER_BG, AMBER_BORDER),
    "open": (BLUE, BLUE_LIGHT, "#C7D2FE"),
    "new": (BLUE, BLUE_LIGHT, "#C7D2FE"),
    "no_action": (GRAY, GRAY_BG, GRAY_BORDER),
    "stopped": (GRAY, GRAY_BG, GRAY_BORDER),
    "closed": (GRAY, GRAY_BG, GRAY_BORDER),
    "unknown": (GRAY, GRAY_BG, GRAY_BORDER),
}


def badge_html(label: str) -> str:
    """Return raw HTML for a semantic pill badge."""
    key = label.strip().lower().replace(" ", "_")
    fg, bg, bd = _BADGE_MAP.get(key, (GRAY, GRAY_BG, GRAY_BORDER))
    return (
        f'<span style="display:inline-flex;align-items:center;padding:3px 10px;'
        f'border-radius:999px;font-family:{FONT};font-size:0.7rem;font-weight:700;'
        f'letter-spacing:0.04em;text-transform:uppercase;background:{bg};color:{fg};'
        f'border:1px solid {bd};line-height:1.5;white-space:nowrap;">{label.upper()}</span>'
    )


def render_badge(label: str) -> None:
    """Render a badge via st.markdown."""
    st.markdown(badge_html(label), unsafe_allow_html=True)


# ─── Card Wrapper ─────────────────────────────────────────────────────────

def card_open(title: str = "") -> None:
    """Open a white card container."""
    t = ""
    if title:
        t = (
            f'<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:0.06em;color:{TEXT_2};padding-bottom:12px;margin-bottom:16px;'
            f'border-bottom:1px solid {BORDER_LIGHT};">{title}</div>'
        )
    st.markdown(
        f'<div style="background:{SURFACE};border:1px solid {BORDER};border-radius:{RADIUS};'
        f'padding:24px;margin-bottom:16px;box-shadow:{SHADOW_SM};">{t}',
        unsafe_allow_html=True,
    )


def card_close() -> None:
    """Close a card container."""
    st.markdown("</div>", unsafe_allow_html=True)


# ─── Timeline / Stepper ──────────────────────────────────────────────────

def _status_colors(status: str) -> tuple[str, str, str]:
    """Return (dot_bg, ring_color, border_color) for a status."""
    s = status.lower()
    if s in ("success", "allow", "allowed", "recovered"):
        return GREEN, GREEN_BG, GREEN
    if s in ("danger", "deny", "denied", "block", "blocked", "default_deny", "failed"):
        return RED, RED_BG, RED
    if s in ("warning", "pending", "in_progress", "escalate"):
        return AMBER, AMBER_BG, AMBER
    if s in ("neutral", "no_action", "stopped", "unknown"):
        return GRAY, GRAY_BG, GRAY
    return BLUE, BLUE_50, BLUE


def render_timeline_step(
    step_num: int,
    title: str,
    content_html: str,
    status: str = "primary",
    is_last: bool = False,
) -> None:
    """Render one step of a numbered vertical timeline stepper."""
    dot_bg, ring_bg, border_left = _status_colors(status)
    line = "" if is_last else f'<div style="width:2px;flex-grow:1;background:{BORDER};min-height:16px;"></div>'

    st.markdown(f"""
<div style="display:flex;gap:16px;margin-bottom:0;">
<div style="display:flex;flex-direction:column;align-items:center;min-width:44px;">
<div style="width:36px;height:36px;border-radius:50%;background:{dot_bg};color:#FFF;
                display:flex;align-items:center;justify-content:center;font-weight:800;
                font-size:0.82rem;font-family:{FONT};flex-shrink:0;box-shadow:0 0 0 4px {ring_bg};z-index:2;">
{step_num}
</div>
{line}
</div>
<div style="flex:1;background:{SURFACE};border:1px solid {BORDER};border-left:3px solid {border_left};
            border-radius:0 {RADIUS} {RADIUS} 0;padding:16px 20px;margin-bottom:12px;
            box-shadow:{SHADOW_SM};transition:all 0.15s ease;"
            onmouseenter="this.style.boxShadow='{SHADOW_MD}';"
            onmouseleave="this.style.boxShadow='{SHADOW_SM}';">
<div style="font-family:{FONT};font-size:0.92rem;font-weight:700;color:{TEXT};
                margin-bottom:8px;">{title}</div>
<div style="font-family:{FONT};font-size:0.85rem;color:{TEXT_2};line-height:1.65;">
{content_html}
</div>
</div>
</div>
    """, unsafe_allow_html=True)


# ─── Styled HTML Table ────────────────────────────────────────────────────

def html_table(headers: list[str], rows: list[list[str]]) -> str:
    """Build a Blade-styled HTML table string."""
    ths = "".join(
        f'<th style="background:{BG};color:{TEXT_2};font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.04em;font-size:0.7rem;padding:10px 14px;border-bottom:1px solid {BORDER};'
        f'text-align:left;font-family:{FONT};">{h}</th>' for h in headers
    )
    trs = ""
    for row in rows:
        tds = "".join(
            f'<td style="padding:10px 14px;border-bottom:1px solid {BORDER_LIGHT};color:{TEXT};'
            f'font-size:0.84rem;font-family:{FONT};">{cell}</td>' for cell in row
        )
        trs += f'<tr style="transition:background 0.1s;" onmouseenter="this.style.background=\'{BLUE_50}\'" onmouseleave="this.style.background=\'transparent\'">{tds}</tr>'
    return (
        f'<table style="width:100%;border-collapse:separate;border-spacing:0;border:1px solid {BORDER};'
        f'border-radius:8px;overflow:hidden;">'
        f'<thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table>'
    )


# ─── Empty State ──────────────────────────────────────────────────────────

def render_empty_state(message: str) -> None:
    """Styled empty state card."""
    st.markdown(f"""
<div style="background:{SURFACE};border:1px solid {BORDER};border-radius:{RADIUS};
        padding:48px 32px;text-align:center;margin:16px 0;">
<div style="font-size:2.5rem;margin-bottom:12px;opacity:0.5;">📭</div>
<div style="font-family:{FONT};font-size:0.92rem;color:{TEXT_2};font-weight:500;">
{message}
</div>
</div>
    """, unsafe_allow_html=True)


# ─── Error State ──────────────────────────────────────────────────────────

def render_error_state(title: str, message: str, correlation_id: str | None = None) -> None:
    """Styled error state card."""
    corr = ""
    if correlation_id:
        corr = f'<div style="font-size:0.72rem;color:{TEXT_3};margin-top:8px;">Correlation ID: <code style="background:{GRAY_BG};padding:2px 6px;border-radius:4px;">{correlation_id}</code></div>'
    st.markdown(f"""
<div style="background:{RED_BG};border:1px solid {RED_BORDER};border-left:4px solid {RED};
        border-radius:0 8px 8px 0;padding:16px 20px;margin:8px 0;">
<div style="font-family:{FONT};font-size:0.92rem;font-weight:700;color:{RED};margin-bottom:4px;">{title}</div>
<div style="font-family:{FONT};font-size:0.85rem;color:{TEXT};">{message}</div>
{corr}
</div>
    """, unsafe_allow_html=True)


# ─── Resilience Test Result Card ──────────────────────────────────────────

def render_resilience_result(
    fault_type: str,
    case_id: str,
    expected: str,
    actual: str,
    result_pass: bool,
) -> None:
    """Styled card for agent resilience test output."""
    fg, bg, bd = (GREEN, GREEN_BG, GREEN_BORDER) if result_pass else (RED, RED_BG, RED_BORDER)
    label = "PASS" if result_pass else "FAIL"
    actual_html = actual.replace("\\n", "<br>").replace("\n", "<br>")
    html_str = f"""
<div style="background:{SURFACE};border:1px solid {BORDER};border-radius:{RADIUS};padding:24px;margin:16px 0;box-shadow:{SHADOW_SM};width:100%;display:flex;flex-direction:column;">
<div style="display:flex;align-items:center;gap:10px;margin-bottom:20px;">
<span style="font-family:{FONT};font-size:1rem;font-weight:800;color:{TEXT};">
Agent Resilience Test
</span>
{badge_html(label)}
</div>
<div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(220px, 1fr));gap:24px;">
<div>
<div style="font-size:0.7rem;font-weight:700;color:{TEXT_2};text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px;">Fault Injected</div>
<code style="background:{GRAY_BG};padding:4px 8px;border-radius:4px;font-size:0.85rem;font-weight:600;color:{TEXT};">{fault_type}</code>
</div>
<div>
<div style="font-size:0.7rem;font-weight:700;color:{TEXT_2};text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px;">Selected Case</div>
<code style="background:{GRAY_BG};padding:4px 8px;border-radius:4px;font-size:0.85rem;font-weight:600;color:{TEXT};font-family:monospace;word-break:break-all;overflow-wrap:anywhere;">{case_id}</code>
</div>
<div>
<div style="font-size:0.7rem;font-weight:700;color:{TEXT_2};text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px;">Expected</div>
<div style="font-size:0.85rem;color:{TEXT};line-height:1.4;">{expected}</div>
</div>
<div>
<div style="font-size:0.7rem;font-weight:700;color:{TEXT_2};text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px;">Actual</div>
<div style="font-size:0.85rem;color:{TEXT};line-height:1.4;">{actual_html}</div>
</div>
</div>
</div>
"""
    st.markdown(html_str, unsafe_allow_html=True)


# ─── Key-Value Detail Row ─────────────────────────────────────────────────

def kv(label: str, value: str) -> str:
    """Return a styled key-value HTML row for use inside cards."""
    return (
        f'<div style="display:flex;align-items:baseline;gap:8px;margin-bottom:6px;">'
        f'<span style="font-size:0.8rem;font-weight:600;color:{TEXT_2};min-width:140px;">{label}</span>'
        f'<span style="font-size:0.88rem;color:{TEXT};font-weight:500;">{value}</span>'
        f'</div>'
    )


def kv_code(label: str, value: str) -> str:
    """Key-value where the value is rendered as code."""
    return (
        f'<div style="display:flex;align-items:baseline;gap:8px;margin-bottom:6px;">'
        f'<span style="font-size:0.8rem;font-weight:600;color:{TEXT_2};min-width:140px;">{label}</span>'
        f'<code style="font-size:0.82rem;background:{GRAY_BG};padding:2px 8px;border-radius:4px;'
        f'color:{TEXT};font-weight:600;">{value}</code></div>'
    )
