"""Settings page displaying current application configuration values."""

import os

import streamlit as st


def render_settings_page() -> None:
    """Render the Settings page with current configuration values."""
    st.title("⚙️ Settings")
    st.markdown("Current application configuration (read-only).")

    aws_region = os.environ.get("AWS_REGION") or "Not configured"
    bedrock_model_id = os.environ.get("BEDROCK_MODEL_ID") or "Not configured"
    log_level = os.environ.get("LOG_LEVEL", "INFO")

    st.text_input("AWS Region", value=aws_region, disabled=True)
    st.text_input("Bedrock Model ID", value=bedrock_model_id, disabled=True)
    st.text_input("Log Level", value=log_level, disabled=True)


render_settings_page()
