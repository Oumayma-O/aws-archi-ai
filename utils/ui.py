"""Shared UI design system for the Streamlit app.

One place for the visual identity: injected CSS (typography, cards, chat
bubbles, dark sidebar), the hero header, and the workflow phase stepper.
Pages call ``inject_css()`` once, then use the small HTML builders.

Palette: AWS "squid ink" navy (#232F3E) + orange (#FF9900) on a warm-white
canvas — deliberately close to the AWS console family so the output reads
as a Solutions-Architect tool, not a generic chatbot.
"""

from __future__ import annotations

import streamlit as st

INK = "#232F3E"
ORANGE = "#FF9900"
CANVAS = "#FFFFFF"
BORDER = "#E7EAF0"
MUTED = "#7A8699"
GREEN = "#1E8E5A"

# NOTE on fonts: the override must NOT hit Streamlit's icon spans —
# icons are ligature fonts (Material Symbols), and overriding their
# font-family renders literal text like "keyboard_double_arrow_right"
# (broken sidebar-collapse arrow, garbled status headers).
_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

body, p, h1, h2, h3, h4, h5, h6, label, li, td, th,
[data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"],
.stButton > button, [data-testid="stChatInput"] textarea,
input, textarea, [data-testid="stMetricValue"] {{
    font-family: 'Inter', 'Source Sans Pro', -apple-system, sans-serif;
}}
[data-testid="stIconMaterial"],
[class*="material-symbols"] {{
    font-family: 'Material Symbols Rounded' !important;
}}

/* ---- chrome ---- */
#MainMenu, footer, [data-testid="stAppDeployButton"] {{ display: none; }}
.block-container {{ padding-top: 3.2rem; max-width: 62rem; }}

/* ---- dark sidebar ---- */
[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, {INK} 0%, #1B2735 100%);
    border-right: none;
}}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
[data-testid="stSidebar"] label, [data-testid="stSidebar"] p,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{
    color: #E8ECF3 !important;
}}
/* page navigation links (Generator / History / Settings) */
[data-testid="stSidebarNav"] a span,
[data-testid="stSidebarNav"] a p {{
    color: #E8ECF3 !important;
    font-weight: 500;
}}
[data-testid="stSidebarNav"] a:hover {{ background: rgba(255,255,255,.08); border-radius: 8px; }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{ background: rgba(255,153,0,.15); border-radius: 8px; }}
[data-testid="stSidebarNav"] a[aria-current="page"] span {{ color: {ORANGE} !important; }}
/* collapse / expand arrows */
[data-testid="stSidebar"] [data-testid="stIconMaterial"],
[data-testid="stSidebarCollapsedControl"] [data-testid="stIconMaterial"] {{
    color: #E8ECF3;
}}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{ color: #9FACC0 !important; }}
[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,.12); }}

/* ---- buttons ---- */
.stButton > button {{
    border-radius: 10px;
    font-weight: 600;
    border: 1px solid {BORDER};
    transition: transform .06s ease, box-shadow .12s ease;
}}
.stButton > button:hover {{ transform: translateY(-1px); box-shadow: 0 4px 14px rgba(35,47,62,.12); }}
.stButton > button[kind="primary"] {{
    background: {ORANGE}; color: {INK}; border: none;
}}

/* ---- chat ---- */
[data-testid="stChatMessage"] {{
    background: {CANVAS};
    border: 1px solid {BORDER};
    border-radius: 16px;
    padding: 1rem 1.15rem;
    box-shadow: 0 1px 3px rgba(35,47,62,.05);
    margin-bottom: .35rem;
}}
[data-testid="stChatInput"] {{ border-radius: 14px; }}

/* ---- cards: metrics, expanders, tabs, status ---- */
[data-testid="stMetric"] {{
    background: {CANVAS};
    border: 1px solid {BORDER};
    border-radius: 14px;
    padding: .9rem 1.1rem;
    box-shadow: 0 1px 3px rgba(35,47,62,.05);
}}
[data-testid="stMetricLabel"] p {{ color: {MUTED}; font-size: .78rem; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; }}
[data-testid="stExpander"] {{
    border: 1px solid {BORDER};
    border-radius: 14px;
    overflow: hidden;
}}
.stTabs [data-baseweb="tab-list"] {{ gap: .25rem; }}
.stTabs [data-baseweb="tab"] {{
    border-radius: 10px 10px 0 0;
    padding: .55rem 1rem;
    font-weight: 600;
}}
[data-testid="stStatus"] {{
    border: 1px solid {BORDER};
    border-radius: 14px;
}}

/* ---- hero ---- */
.aai-hero {{
    background: linear-gradient(120deg, {INK} 0%, #2C3E54 70%, #38506C 100%);
    border-radius: 18px;
    padding: 1.35rem 1.7rem 1.25rem;
    margin-bottom: 1rem;
    color: #fff;
}}
.aai-hero h1 {{
    color: #fff;
    font-size: 1.45rem;
    font-weight: 700;
    letter-spacing: -.01em;
    margin: 0 0 .3rem;
    padding: 0;
}}
.aai-hero p {{ color: #B9C4D4; margin: 0; font-size: .92rem; max-width: 46rem; }}

/* ---- phase stepper ---- */
.aai-stepper {{
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: .1rem;
    margin: .2rem 0 1rem;
}}
.aai-step {{
    display: flex;
    align-items: center;
    gap: .42rem;
    padding: .3rem .75rem;
    border-radius: 999px;
    font-size: .78rem;
    font-weight: 600;
    color: {MUTED};
}}
.aai-step .dot {{ width: 8px; height: 8px; border-radius: 50%; background: #CBD2DC; }}
.aai-step.done {{ color: {GREEN}; }}
.aai-step.done .dot {{ background: {GREEN}; }}
.aai-step.current {{
    color: {INK};
    background: rgba(255,153,0,.13);
    border: 1px solid rgba(255,153,0,.45);
}}
.aai-step.current .dot {{
    background: {ORANGE};
    animation: aai-pulse 1.4s infinite;
}}
.aai-connector {{ color: #D4DAE3; font-size: .7rem; margin: 0 .05rem; }}
@keyframes aai-pulse {{
    0%   {{ box-shadow: 0 0 0 0 rgba(255,153,0,.45); }}
    70%  {{ box-shadow: 0 0 0 6px rgba(255,153,0,0); }}
    100% {{ box-shadow: 0 0 0 0 rgba(255,153,0,0); }}
}}
</style>
"""


def inject_css() -> None:
    """Inject the app-wide stylesheet. Call once per page render."""
    st.markdown(_CSS, unsafe_allow_html=True)


def hero(title: str, subtitle: str) -> None:
    """Render the gradient hero header."""
    st.markdown(
        f"""
        <div class="aai-hero">
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# Workflow steps in display order: (phase values it covers, label)
_STEPS: list[tuple[tuple[str, ...], str]] = [
    (("requirements_analysis",), "Describe"),
    (("clarification",), "Clarify"),
    (("research",), "Research"),
    (("design",), "Design"),
    (("diagram_generation",), "Diagram"),
    (("review",), "Review"),
    (("final_report", "complete"), "Report"),
]


def phase_stepper_html(current_phase: str) -> str:
    """Build the stepper HTML for a phase — render into an st.empty() slot
    so it can be live-updated mid-run as PHASE_TRANSITION events arrive."""
    current_idx = next(
        (i for i, (phases, _) in enumerate(_STEPS) if current_phase in phases), 0
    )
    all_done = current_phase == "complete"

    chips: list[str] = []
    for i, (_, label) in enumerate(_STEPS):
        if all_done or i < current_idx:
            chips.append(f'<span class="aai-step done"><span class="dot"></span>{label}</span>')
        elif i == current_idx:
            chips.append(f'<span class="aai-step current"><span class="dot"></span>{label}</span>')
        else:
            chips.append(f'<span class="aai-step"><span class="dot"></span>{label}</span>')
        if i < len(_STEPS) - 1:
            chips.append('<span class="aai-connector">›</span>')

    return f'<div class="aai-stepper">{"".join(chips)}</div>'
