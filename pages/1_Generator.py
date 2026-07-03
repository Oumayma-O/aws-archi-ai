"""Generator page - orchestrates the full architecture generation workflow.

Features streaming output, Graphviz diagram visualization, and download buttons.
"""

import json
import logging
import os
import sys
import traceback
import time

import streamlit as st
from pydantic import ValidationError

from models.architecture import ArchitectureModel
from services.bedrock import invoke_model_stream
from services.diagram import to_drawio_xml, to_graphviz, to_mermaid
from services.cost import format_cost_summary
from services.exceptions import (
    BedrockConnectionError,
    BedrockThrottlingError,
    BedrockTimeoutError,
    JsonExtractionError,
)
from services.parser import extract_json, parse_architecture
from services.prompt_builder import build_prompt
from utils.export import generate_export_filename
from utils.validation import validate_input

logger = logging.getLogger(__name__)


def _init_session_state() -> None:
    """Initialize session state keys if not already present."""
    if "user_input" not in st.session_state:
        st.session_state.user_input = ""
    if "current_architecture" not in st.session_state:
        st.session_state.current_architecture = None
    if "history" not in st.session_state:
        st.session_state.history = []
    if "generation_error" not in st.session_state:
        st.session_state.generation_error = None
    if "raw_response" not in st.session_state:
        st.session_state.raw_response = None


def _render_sidebar() -> tuple[str, str, float, bool]:
    """Render sidebar controls and return selected values."""
    with st.sidebar:
        st.header("Generation Settings")

        provider = st.selectbox("Provider", options=["Amazon Bedrock"], index=0)
        model = st.selectbox("Model", options=["Claude Haiku 4.5", "Claude Sonnet 4.5"], index=0)
        temperature = st.slider("Temperature", min_value=0.0, max_value=1.0, value=1.0, step=0.1)
        generate_clicked = st.button("🚀 Generate", type="primary", use_container_width=True)

    return provider, model, temperature, generate_clicked


def _get_model_id(model_name: str) -> str:
    """Map display model name to Bedrock model ID.
    
    Uses BEDROCK_MODEL_ID env var as the default, adjusting prefix based on region.
    """
    region = os.environ.get("AWS_REGION", "eu-west-1")
    prefix = "eu" if region.startswith("eu") else "us"
    
    model_map = {
        "Claude Haiku 4.5": f"{prefix}.anthropic.claude-haiku-4-5-20251001-v1:0",
        "Claude Sonnet 4.5": f"{prefix}.anthropic.claude-sonnet-4-5-20250929-v1:0",
    }
    return model_map.get(model_name, os.environ.get(
        "BEDROCK_MODEL_ID", f"{prefix}.anthropic.claude-haiku-4-5-20251001-v1:0"
    ))


def handle_generate(description: str, temperature: float, model_id: str) -> None:
    """Run the generation pipeline with streaming output."""
    # Validate input
    if not validate_input(description):
        st.error("Please enter a system description. The input cannot be empty.")
        return
    if len(description) > 5000:
        st.error(f"Description exceeds 5000 characters (current: {len(description)}).")
        return

    st.session_state.generation_error = None

    try:
        # Step 1: Build prompt
        prompt = build_prompt(description)

        # Step 2: Stream response with live display
        st.markdown("#### ⏳ Generating architecture...")
        progress_bar = st.progress(0, text="Connecting to Bedrock...")
        response_container = st.empty()

        full_response = ""
        start_time = time.time()

        for chunk in invoke_model_stream(
            prompt=prompt,
            model_id=model_id,
            temperature=temperature,
        ):
            full_response += chunk
            elapsed = time.time() - start_time
            progress_bar.progress(
                min(0.9, elapsed / 30),  # estimate ~30s total
                text=f"Receiving response... ({elapsed:.0f}s, {len(full_response)} chars)"
            )
            # Show streaming text
            response_container.code(full_response[-500:] if len(full_response) > 500 else full_response, language="json")

        progress_bar.progress(1.0, text="✅ Response received! Parsing...")
        response_container.empty()

        # Store raw response
        st.session_state.raw_response = full_response
        print(f"[GENERATE] Response received: {len(full_response)} chars in {time.time()-start_time:.1f}s", file=sys.stderr, flush=True)

        # Step 3: Extract JSON
        json_str = extract_json(full_response)

        # Step 4: Parse and validate
        architecture = parse_architecture(json_str)

        # Step 5: Store results
        st.session_state.current_architecture = architecture
        st.session_state.history.insert(0, architecture)

        progress_bar.empty()
        st.success(f"✅ Architecture generated: **{architecture.title}**")

    except BedrockConnectionError as e:
        logger.error("Bedrock connection failed", exc_info=True)
        st.session_state.generation_error = "connection"
        st.error("❌ Unable to connect to AWS Bedrock. Check your network and credentials.")

    except BedrockThrottlingError:
        logger.error("Bedrock request throttled", exc_info=True)
        st.session_state.generation_error = "throttling"
        st.error("⚠️ Request was throttled. Please wait a few seconds and try again.")

    except BedrockTimeoutError:
        logger.error("Bedrock request timed out", exc_info=True)
        st.session_state.generation_error = "timeout"
        st.error("⏱️ Request timed out. Please try again.")

    except JsonExtractionError:
        logger.error("JSON extraction failed", exc_info=True)
        st.session_state.generation_error = "parse"
        st.error("❌ Could not extract valid JSON from the response. Click Retry.")

    except ValidationError as e:
        logger.error("Response validation failed", exc_info=True)
        st.session_state.generation_error = "validation"
        st.error("❌ AI response was malformed. Click Retry.")

    except Exception:
        logger.error("Unhandled exception:\n%s", traceback.format_exc())
        print(f"[GENERATE] ERROR: {traceback.format_exc()}", file=sys.stderr, flush=True)
        st.session_state.generation_error = "unexpected"
        st.error("❌ An unexpected error occurred. Please try again.")


def display_results(architecture: ArchitectureModel) -> None:
    """Render architecture results with Graphviz diagram and download buttons."""
    st.markdown("---")
    st.header(architecture.title)
    st.markdown(architecture.summary)

    tabs = st.tabs(["📊 Diagram", "🏗️ Overview", "☁️ Services", "🔒 Security", "💰 Cost", "📥 Exports"])

    # DIAGRAM TAB (first for impact)
    with tabs[0]:
        nodes = architecture.diagram.nodes
        connections = architecture.diagram.connections

        if not nodes:
            st.info("No diagram data available.")
        else:
            # Generate AWS diagram with official icons
            from services.aws_diagram import generate_aws_diagram

            with st.spinner("Rendering AWS diagram..."):
                png_bytes = generate_aws_diagram(nodes, connections, architecture.title)

            if png_bytes:
                st.image(png_bytes, use_container_width=True)
            else:
                # Fallback to Graphviz
                dot_code = to_graphviz(nodes, connections)
                st.graphviz_chart(dot_code, use_container_width=True)

            # Download button — Draw.io only
            drawio_xml = to_drawio_xml(nodes, connections)
            st.download_button(
                "📐 Download Draw.io (.drawio)",
                data=drawio_xml,
                file_name=generate_export_filename(architecture.title, "drawio", "drawio"),
                mime="application/xml",
            )

    # OVERVIEW TAB
    with tabs[1]:
        st.subheader("Architecture Description")
        st.write(architecture.architecture_description)
        if architecture.recommendations:
            st.subheader("Recommendations")
            for rec in architecture.recommendations:
                st.markdown(f"✅ {rec}")

    # SERVICES TAB
    with tabs[2]:
        if not architecture.aws_services:
            st.info("No service data available.")
        else:
            for svc in architecture.aws_services:
                st.markdown(f"**{svc.name}** — {svc.role}")

    # SECURITY TAB
    with tabs[3]:
        security = architecture.security
        has_data = any([security.iam_policies, security.encryption, security.cloudtrail, security.waf_rules, security.recommendations])
        if not has_data:
            st.info("No security data available.")
        else:
            if security.iam_policies:
                st.subheader("IAM Policies")
                for p in security.iam_policies:
                    st.markdown(f"- {p}")
            if security.encryption:
                st.subheader("Encryption")
                for e in security.encryption:
                    st.markdown(f"- {e}")
            if security.recommendations:
                st.subheader("Security Recommendations")
                for r in security.recommendations:
                    st.markdown(f"- {r}")

    # COST TAB
    with tabs[4]:
        cost = architecture.estimated_cost
        if not cost.total_monthly:
            st.info("No cost data available.")
        else:
            st.metric("💰 Estimated Monthly Cost", cost.total_monthly)
            if cost.breakdown:
                st.subheader("Per-Service Breakdown")
                cost_data = [{"Service": s.service, "Monthly Cost": s.monthly_cost} for s in cost.breakdown]
                st.table(cost_data)

    # EXPORTS TAB
    with tabs[5]:
        col1, col2 = st.columns(2)
        with col1:
            json_data = architecture.model_dump_json(indent=2)
            st.download_button(
                "📋 Architecture JSON",
                data=json_data,
                file_name=generate_export_filename(architecture.title, "architecture", "json"),
                mime="application/json",
            )
        with col2:
            if st.session_state.raw_response:
                st.download_button(
                    "📝 Raw LLM Response",
                    data=st.session_state.raw_response,
                    file_name="raw_response.txt",
                    mime="text/plain",
                )


def render_generator_page() -> None:
    """Render the Generator page."""
    _init_session_state()

    st.title("🏗️ Architecture Generator")
    st.markdown("Describe your system and generate a production-ready AWS architecture.")

    # Sidebar
    provider, model, temperature, generate_clicked = _render_sidebar()
    model_id = _get_model_id(model)

    # Input area
    description = st.text_area(
        "Describe your system",
        value=st.session_state.user_input,
        height=150,
        max_chars=5000,
        placeholder="e.g., A web application with React frontend, Node.js API, PostgreSQL database, handling 10k concurrent users...",
    )
    st.session_state.user_input = description

    # Generate
    if generate_clicked:
        print(f"[GENERATE] Button clicked! model={model_id}", file=sys.stderr, flush=True)
        handle_generate(description, temperature, model_id)

    # Show results
    if st.session_state.current_architecture:
        display_results(st.session_state.current_architecture)

    # Retry button
    if st.session_state.generation_error:
        if st.button("🔄 Retry"):
            handle_generate(description, temperature, model_id)


# Run the page
render_generator_page()
