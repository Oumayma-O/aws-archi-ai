"""AWS Architect AI - Streamlit application entry point."""

from dotenv import load_dotenv

load_dotenv()

from utils.logging import setup_logging

setup_logging()

import streamlit as st

from utils.ui import hero, inject_css

st.set_page_config(
    page_title="AWS Architect AI",
    page_icon="🏗️",
    layout="wide",
)

inject_css()

hero(
    "AWS Architect AI",
    "From a plain-language description to a Solutions-Architect deliverable: "
    "clarified requirements, researched services, a Well-Architected design, "
    "and an exportable diagram.",
)

c1, c2, c3 = st.columns(3)
with c1:
    with st.container(border=True):
        st.markdown("#### ❓ Discovery interview")
        st.caption(
            "A clarification agent asks workload-specific questions — PCI scope "
            "for payments, traffic shape, budget — and never re-asks what you've "
            "already answered."
        )
with c2:
    with st.container(border=True):
        st.markdown("#### 📚 Live research")
        st.caption(
            "AWS documentation and pricing MCP servers feed the design with "
            "current services and real prices — flagged honestly as estimates "
            "when sources are offline."
        )
with c3:
    with st.container(border=True):
        st.markdown("#### 🏗️ Architect-grade output")
        st.caption(
            "Full request path, VPC decision rationale, cost comparisons, "
            "Well-Architected review, IaC skeleton, and a draw.io diagram."
        )

st.markdown(" ")
if st.button("🚀 Open the Generator", type="primary"):
    st.switch_page("pages/1_Generator.py")
