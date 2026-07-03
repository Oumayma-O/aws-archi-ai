"""Generator page - orchestrates the full architecture generation workflow.

Features streaming output, Graphviz diagram visualization, and download buttons.
Supports two modes: Quick Generate (single-shot) and Architect Mode (agentic workflow).
"""

import asyncio
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
    if "generation_mode" not in st.session_state:
        st.session_state.generation_mode = "Quick Generate"


def _render_sidebar() -> tuple[str, str, float, bool]:
    """Render sidebar controls and return selected values."""
    with st.sidebar:
        st.header("Generation Settings")

        # Mode selector
        mode = st.radio(
            "Generation Mode",
            options=["Quick Generate", "Architect Mode"],
            index=0 if st.session_state.generation_mode == "Quick Generate" else 1,
            help="Quick Generate: single-shot architecture generation. Architect Mode: multi-turn conversational workflow with research and clarification.",
            key="mode_selector",
        )
        st.session_state.generation_mode = mode

        st.divider()

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


def render_quick_generate_mode(model_id: str, temperature: float, generate_clicked: bool) -> None:
    """Render the existing Quick Generate interface (unchanged logic).
    
    This wraps the original single-shot generation pipeline: text area input,
    generate button, streaming response, and results display.
    """
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


def render_architect_mode() -> None:
    """Render the chat-based Architect Mode interface.

    Displays the multi-turn conversational workflow powered by the Orchestrator Agent.
    This includes conversation history, streaming agent responses, workflow phase
    indicator, and inline artifacts.
    """
    from agents.events import AgentEvent, AgentEventType
    from agents.orchestrator import OrchestratorAgent
    from models.session import WorkflowPhase

    # --- Session State Initialization ---
    if "architect_messages" not in st.session_state:
        st.session_state.architect_messages = []
    if "architect_session" not in st.session_state:
        st.session_state.architect_session = None
    if "architect_phase" not in st.session_state:
        st.session_state.architect_phase = WorkflowPhase.REQUIREMENTS_ANALYSIS
    if "architect_report" not in st.session_state:
        st.session_state.architect_report = None
    if "architect_processing" not in st.session_state:
        st.session_state.architect_processing = False

    # --- Phase Indicator ---
    phase_labels = {
        WorkflowPhase.REQUIREMENTS_ANALYSIS: "📝 Requirements Analysis",
        WorkflowPhase.CLARIFICATION: "❓ Clarification",
        WorkflowPhase.RESEARCH: "🔍 Research",
        WorkflowPhase.DESIGN: "🏗️ Design",
        WorkflowPhase.DIAGRAM_GENERATION: "📊 Diagram Generation",
        WorkflowPhase.REVIEW: "✅ Review",
        WorkflowPhase.FINAL_REPORT: "📋 Final Report",
        WorkflowPhase.COMPLETE: "🎉 Complete",
    }
    current_phase = st.session_state.architect_phase
    phase_label = phase_labels.get(current_phase, str(current_phase))
    st.caption(f"Phase: {phase_label}")

    # --- Display Conversation History ---
    for msg in st.session_state.architect_messages:
        role = msg["role"]
        content = msg["content"]
        artifacts = msg.get("artifacts", [])

        with st.chat_message(role):
            st.markdown(content)

            # Render inline artifacts
            for artifact in artifacts:
                _render_inline_artifact(artifact)

    # --- Final Report Tabbed View ---
    if st.session_state.architect_report is not None:
        _render_report_tabs(st.session_state.architect_report)

    # --- Chat Input ---
    # Determine if the system is in a non-interactive phase
    non_interactive_phases = {
        WorkflowPhase.RESEARCH,
        WorkflowPhase.DESIGN,
        WorkflowPhase.DIAGRAM_GENERATION,
        WorkflowPhase.REVIEW,
    }
    is_processing = st.session_state.architect_processing

    if is_processing and current_phase in non_interactive_phases:
        placeholder_text = f"Agent is working ({phase_label})... messages will be queued"
    elif current_phase == WorkflowPhase.COMPLETE:
        placeholder_text = "Architecture complete. Start a new session from the sidebar."
    else:
        placeholder_text = "Describe your system or answer the agent's questions..."

    user_input = st.chat_input(placeholder_text)

    if user_input:
        # Add user message to history
        st.session_state.architect_messages.append(
            {"role": "user", "content": user_input, "phase": current_phase.value, "artifacts": []}
        )

        # Display user message immediately
        with st.chat_message("user"):
            st.markdown(user_input)

        # Process the message through the orchestrator
        _process_architect_message(user_input)


def _process_architect_message(user_message: str) -> None:
    """Process a user message through the OrchestratorAgent.

    Creates or reuses an OrchestratorAgent, runs the message through it,
    and streams the resulting events into the chat interface.

    Args:
        user_message: The user's input text.
    """
    from agents.events import AgentEvent, AgentEventType
    from agents.orchestrator import OrchestratorAgent
    from models.session import WorkflowPhase

    st.session_state.architect_processing = True

    # Create or reuse the orchestrator agent
    if st.session_state.architect_session is None:
        agent = OrchestratorAgent()
        st.session_state.architect_session = agent
    else:
        agent = st.session_state.architect_session

    # Run the agent and collect events
    try:
        events = _run_agent_async(agent, user_message)
    except Exception as exc:
        st.session_state.architect_processing = False
        with st.chat_message("assistant"):
            st.error(f"An error occurred: {exc}")
        st.session_state.architect_messages.append(
            {
                "role": "assistant",
                "content": f"❌ An error occurred: {exc}",
                "phase": st.session_state.architect_phase.value,
                "artifacts": [],
            }
        )
        return

    # Process events and build assistant response
    assistant_text_parts: list[str] = []
    artifacts: list[dict] = []

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        accumulated_text = ""

        for event in events:
            if event.type == AgentEventType.TEXT_CHUNK:
                text_data = event.data if isinstance(event.data, str) else str(event.data)
                accumulated_text += text_data + "\n"
                message_placeholder.markdown(accumulated_text)
                assistant_text_parts.append(text_data)

            elif event.type == AgentEventType.PHASE_TRANSITION:
                if isinstance(event.data, dict):
                    new_phase_str = event.data.get("to_phase", "")
                    try:
                        new_phase = WorkflowPhase(new_phase_str)
                        st.session_state.architect_phase = new_phase
                    except ValueError:
                        pass

            elif event.type == AgentEventType.ARTIFACT:
                artifact_data = event.data if isinstance(event.data, dict) else {"content": event.data}
                artifacts.append(artifact_data)
                _render_inline_artifact(artifact_data)

            elif event.type == AgentEventType.ERROR:
                error_msg = ""
                if isinstance(event.data, dict):
                    error_msg = event.data.get("message", str(event.data))
                else:
                    error_msg = str(event.data)
                st.warning(error_msg)
                assistant_text_parts.append(f"⚠️ {error_msg}")

            elif event.type == AgentEventType.COMPLETE:
                # Store the final report if available
                session = agent.get_session()
                if session.architecture_report is not None:
                    st.session_state.architect_report = session.architecture_report

    # Store the assistant message in history
    final_text = "\n".join(assistant_text_parts) if assistant_text_parts else ""
    if final_text or artifacts:
        st.session_state.architect_messages.append(
            {
                "role": "assistant",
                "content": final_text,
                "phase": st.session_state.architect_phase.value,
                "artifacts": artifacts,
            }
        )

    st.session_state.architect_processing = False

    # Rerun to update the phase indicator and show the report tabs if complete
    if st.session_state.architect_phase == WorkflowPhase.COMPLETE:
        st.rerun()


def _run_agent_async(agent, user_message: str) -> list:
    """Bridge async OrchestratorAgent.run() with sync Streamlit.

    Uses asyncio.run() to execute the async generator and collect all events.

    Args:
        agent: The OrchestratorAgent instance.
        user_message: The user's input text.

    Returns:
        List of AgentEvent objects collected from the async generator.
    """

    async def _collect_events():
        events = []
        async for event in agent.run(user_message):
            events.append(event)
        return events

    # Use asyncio.run() for a clean event loop
    # Handle case where event loop already exists (e.g., Jupyter/Streamlit)
    try:
        loop = asyncio.get_running_loop()
        # If we're already in an async context, create a new thread
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            events = loop.run_in_executor(pool, asyncio.run, _collect_events())
            # This won't work directly; fall back to new loop
            raise RuntimeError("Use new loop")
    except RuntimeError:
        return asyncio.run(_collect_events())


def _render_inline_artifact(artifact: dict) -> None:
    """Render an artifact inline within the chat conversation.

    Supports diagram artifacts (Draw.io XML, PNG) and architecture reports
    (rendered as summary tables).

    Args:
        artifact: Dict with artifact data including 'type' and 'content' fields.
    """
    artifact_type = artifact.get("type", "")

    if artifact_type == "diagram":
        # Render diagram inline
        content = artifact.get("content", "")
        has_png = artifact.get("has_png", False)

        if has_png and isinstance(content, bytes):
            st.image(content, caption="Architecture Diagram", use_container_width=True)
        elif content and isinstance(content, str):
            # Show Draw.io XML as downloadable code
            with st.expander("📊 Architecture Diagram (Draw.io XML)"):
                st.code(content, language="xml")
                st.download_button(
                    "📐 Download Draw.io (.drawio)",
                    data=content,
                    file_name="architecture.drawio",
                    mime="application/xml",
                    key=f"diagram_download_{time.time()}",
                )

    elif artifact_type == "architecture_report":
        # Render a cost table / summary inline
        content = artifact.get("content", {})
        title = artifact.get("title", "Architecture Report")

        with st.expander(f"📋 {title}"):
            if isinstance(content, dict):
                # Show cost breakdown if available
                estimated_cost = content.get("estimated_cost", {})
                if estimated_cost:
                    total = estimated_cost.get("total_monthly", "N/A")
                    st.metric("Estimated Monthly Cost", total)

                    breakdown = estimated_cost.get("breakdown", [])
                    if breakdown:
                        cost_data = [
                            {"Service": item.get("service", ""), "Monthly Cost": item.get("monthly_cost", "")}
                            for item in breakdown
                        ]
                        st.table(cost_data)

                # Show cost comparisons
                cost_comparisons = content.get("cost_comparisons", [])
                if cost_comparisons:
                    st.subheader("Cost Comparisons")
                    for comp in cost_comparisons:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"**{comp.get('approach_a', '')}**: {comp.get('approach_a_monthly', '')}")
                        with col2:
                            st.markdown(f"**{comp.get('approach_b', '')}**: {comp.get('approach_b_monthly', '')}")
                        st.caption(f"Recommendation: {comp.get('recommendation', '')} — {comp.get('reasoning', '')}")
            else:
                st.json(content)

    else:
        # Generic artifact: show as JSON
        with st.expander(f"📎 Artifact: {artifact_type}"):
            st.json(artifact)


def _render_report_tabs(report) -> None:
    """Render the final ArchitectureReport in a tabbed results view.

    This mirrors the existing display_results() pattern but uses the
    ArchitectureReport model from Architect Mode.

    Args:
        report: An ArchitectureReport instance.
    """
    st.markdown("---")
    st.header(f"📋 {report.title}")
    st.markdown(report.summary)

    tabs = st.tabs(["📊 Diagram", "🏗️ Overview", "☁️ Services", "🔒 Security", "💰 Cost", "✅ WAF Review", "📥 Exports"])

    # DIAGRAM TAB
    with tabs[0]:
        nodes = report.diagram.nodes
        connections = report.diagram.connections

        if not nodes:
            st.info("No diagram data available.")
        else:
            from services.aws_diagram import generate_aws_diagram

            with st.spinner("Rendering AWS diagram..."):
                png_bytes = generate_aws_diagram(nodes, connections, report.title)

            if png_bytes:
                st.image(png_bytes, use_container_width=True)
            else:
                dot_code = to_graphviz(nodes, connections)
                st.graphviz_chart(dot_code, use_container_width=True)

            drawio_xml = to_drawio_xml(nodes, connections)
            st.download_button(
                "📐 Download Draw.io (.drawio)",
                data=drawio_xml,
                file_name=generate_export_filename(report.title, "drawio", "drawio"),
                mime="application/xml",
            )

    # OVERVIEW TAB
    with tabs[1]:
        st.subheader("Architecture Description")
        st.write(report.architecture_description)

        if report.recommendations:
            st.subheader("Recommendations")
            for rec in report.recommendations:
                st.markdown(f"✅ {rec}")

        if report.rationale:
            st.subheader("Design Rationale")
            for r in report.rationale:
                with st.expander(f"**{r.decision}** → {r.chosen_option}"):
                    st.write(r.reasoning)
                    if r.alternatives_considered:
                        st.caption(f"Alternatives: {', '.join(r.alternatives_considered)}")

        if report.assumptions:
            st.subheader("Assumptions")
            for assumption in report.assumptions:
                st.markdown(f"- {assumption}")

    # SERVICES TAB
    with tabs[2]:
        if not report.aws_services:
            st.info("No service data available.")
        else:
            for svc in report.aws_services:
                st.markdown(f"**{svc.name}** — {svc.role}")

    # SECURITY TAB
    with tabs[3]:
        security = report.security
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

        # VPC Design
        if report.vpc_design:
            st.subheader("VPC Design")
            vpc = report.vpc_design
            st.markdown(f"**CIDR:** {vpc.cidr_block}")
            st.markdown(f"**Public Subnets:** {len(vpc.public_subnets)} | **Private Subnets:** {len(vpc.private_subnets)}")
            st.markdown(f"**NAT Gateways:** {', '.join(vpc.nat_gateways) if vpc.nat_gateways else 'None'}")
            if vpc.security_groups:
                st.markdown(f"**Security Groups:** {len(vpc.security_groups)}")
            if vpc.validation_notes:
                st.caption("Validation: " + "; ".join(vpc.validation_notes))

    # COST TAB
    with tabs[4]:
        cost = report.estimated_cost
        if not cost.total_monthly:
            st.info("No cost data available.")
        else:
            st.metric("💰 Estimated Monthly Cost", cost.total_monthly)
            if cost.breakdown:
                st.subheader("Per-Service Breakdown")
                cost_data = [{"Service": s.service, "Monthly Cost": s.monthly_cost} for s in cost.breakdown]
                st.table(cost_data)

        if report.cost_comparisons:
            st.subheader("Cost Comparisons")
            for comp in report.cost_comparisons:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**{comp.approach_a}**: {comp.approach_a_monthly}")
                with col2:
                    st.markdown(f"**{comp.approach_b}**: {comp.approach_b_monthly}")
                st.caption(f"💡 {comp.recommendation} — {comp.reasoning}")
                st.divider()

    # WELL-ARCHITECTED REVIEW TAB
    with tabs[5]:
        review = report.well_architected_review
        if review is None:
            st.info("No Well-Architected review available.")
        else:
            pillars = [
                ("Operational Excellence", review.operational_excellence),
                ("Security", review.security),
                ("Reliability", review.reliability),
                ("Performance Efficiency", review.performance_efficiency),
                ("Cost Optimization", review.cost_optimization),
                ("Sustainability", review.sustainability),
            ]
            for pillar_name, items in pillars:
                if items:
                    st.subheader(pillar_name)
                    for item in items:
                        st.markdown(f"- {item}")

            if review.violations:
                st.subheader("⚠️ Violations")
                for v in review.violations:
                    st.markdown(f"- {v}")

            if review.improvement_opportunities:
                st.subheader("💡 Improvement Opportunities")
                for opp in review.improvement_opportunities:
                    st.markdown(f"- {opp}")

    # EXPORTS TAB
    with tabs[6]:
        col1, col2 = st.columns(2)
        with col1:
            json_data = report.model_dump_json(indent=2)
            st.download_button(
                "📋 Architecture JSON",
                data=json_data,
                file_name=generate_export_filename(report.title, "architecture_report", "json"),
                mime="application/json",
            )
        with col2:
            # Export as markdown summary
            md_content = _report_to_markdown(report)
            st.download_button(
                "📝 Markdown Report",
                data=md_content,
                file_name=generate_export_filename(report.title, "report", "md"),
                mime="text/markdown",
            )

        if report.iac_skeleton:
            st.subheader("Infrastructure as Code Skeleton")
            st.code(report.iac_skeleton, language="hcl")
            st.download_button(
                "🏗️ Download IaC Skeleton",
                data=report.iac_skeleton,
                file_name="infrastructure_skeleton.tf",
                mime="text/plain",
            )


def _report_to_markdown(report) -> str:
    """Convert an ArchitectureReport to a Markdown document.

    Args:
        report: An ArchitectureReport instance.

    Returns:
        Markdown string representation of the report.
    """
    lines = [
        f"# {report.title}",
        "",
        report.summary,
        "",
        "## Architecture Description",
        "",
        report.architecture_description,
        "",
        "## AWS Services",
        "",
    ]
    for svc in report.aws_services:
        lines.append(f"- **{svc.name}**: {svc.role}")
    lines.append("")

    if report.estimated_cost.total_monthly:
        lines.append("## Cost Estimate")
        lines.append("")
        lines.append(f"**Total Monthly:** {report.estimated_cost.total_monthly}")
        lines.append("")
        if report.estimated_cost.breakdown:
            lines.append("| Service | Monthly Cost |")
            lines.append("|---------|-------------|")
            for item in report.estimated_cost.breakdown:
                lines.append(f"| {item.service} | {item.monthly_cost} |")
            lines.append("")

    if report.recommendations:
        lines.append("## Recommendations")
        lines.append("")
        for rec in report.recommendations:
            lines.append(f"- {rec}")
        lines.append("")

    if report.well_architected_review:
        lines.append("## Well-Architected Review")
        lines.append("")
        review = report.well_architected_review
        if review.violations:
            lines.append("### Violations")
            for v in review.violations:
                lines.append(f"- {v}")
            lines.append("")
        if review.improvement_opportunities:
            lines.append("### Improvement Opportunities")
            for opp in review.improvement_opportunities:
                lines.append(f"- {opp}")
            lines.append("")

    return "\n".join(lines)


def render_generator_page() -> None:
    """Render the Generator page with mode selection."""
    _init_session_state()

    st.title("🏗️ Architecture Generator")
    st.markdown("Describe your system and generate a production-ready AWS architecture.")

    # Sidebar (includes mode selector + model/temperature controls)
    provider, model, temperature, generate_clicked = _render_sidebar()
    model_id = _get_model_id(model)

    # Route to the appropriate mode
    if st.session_state.generation_mode == "Quick Generate":
        render_quick_generate_mode(model_id, temperature, generate_clicked)
    else:
        render_architect_mode()


# Run the page
render_generator_page()
