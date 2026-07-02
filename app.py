"""AWS Architect AI - Streamlit application entry point."""

from dotenv import load_dotenv

load_dotenv()

from utils.logging import setup_logging

setup_logging()

import streamlit as st

st.set_page_config(
    page_title="AWS Architect AI",
    page_icon="🏗️",
    layout="wide",
)

st.title("AWS Architect AI")
st.markdown(
    "Generate production-ready AWS architectures from natural language descriptions."
)
