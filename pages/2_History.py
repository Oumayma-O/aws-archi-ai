"""History page for AWS Architect AI.

Displays session-based generation history, allowing users to browse and
review previously generated architectures in the same tabbed format
used for new generations.
"""

import streamlit as st

from models.architecture import ArchitectureModel
from services.cost import format_cost_summary
from services.diagram import to_drawio_xml, to_mermaid
from utils.export import generate_export_filename


def render_history_page() -> None:
    """Render the History page showing past generations."""
    st.title("Generation History")

    # Initialize history in session state if not present
    if "history" not in st.session_state:
        st.session_state.history = []

    history: list[dict] = st.session_state.history

    if history:
        # History is already ordered most recent first (Generator inserts at index 0)
        titles = [_get_title(entry) for entry in history]

        # Sidebar selection with architecture titles
        selected_title = st.sidebar.selectbox(
            "Previous Generations",
            options=titles,
            index=0,
        )

        # Find the selected architecture
        selected_index = titles.index(selected_title)
        entry = history[selected_index]
        architecture = _get_architecture(entry)

        # Display selected architecture in tabbed format
        _display_architecture(architecture)
    else:
        st.info("No Quick Generate architectures in this browser session yet.")

    _render_architect_sessions()


def _render_architect_sessions() -> None:
    """List persisted Architect Mode sessions from the DynamoDB store.

    Read-only view over what the orchestrator saves after every phase
    transition: title, phase, last activity, and — for completed sessions —
    the stored architecture report as downloadable JSON.
    """
    import asyncio

    st.divider()
    st.subheader("💾 Architect Mode Sessions")
    st.caption("Persisted across restarts (DynamoDB `architect-sessions`).")

    try:
        from agents.session_store import SessionStore

        store = SessionStore()
        summaries = asyncio.run(store.list_sessions("default"))
    except Exception as exc:
        st.warning(f"Session store unavailable: {exc}")
        return

    if not summaries:
        st.info("No persisted sessions yet. Complete a run in Architect Mode first.")
        return

    for summary in summaries[:20]:
        label = (
            f"{summary.title} — {summary.current_phase.value} · "
            f"{summary.updated_at:%Y-%m-%d %H:%M}"
        )
        with st.expander(label):
            st.caption(f"Session ID: `{summary.session_id}`")
            try:
                session = asyncio.run(store.load(summary.session_id))
            except Exception as exc:
                st.warning(f"Could not load session: {exc}")
                continue
            if session is None:
                st.info("Session data not found.")
                continue

            report = session.architecture_report
            if report is None:
                st.info("No architecture report yet — session did not reach the design phase.")
                continue

            # Report round-trips through JSON in DynamoDB, so it arrives as
            # a plain dict here.
            title = report.get("title", "Architecture Report") if isinstance(report, dict) else str(report)
            summary_text = report.get("summary", "") if isinstance(report, dict) else ""
            st.markdown(f"**{title}**")
            if summary_text:
                st.write(summary_text.replace("$", "\\$"))

            import json

            st.download_button(
                "📋 Download report JSON",
                data=json.dumps(report, indent=2, default=str),
                file_name=f"architecture_{summary.session_id[:8]}.json",
                mime="application/json",
                key=f"dl_{summary.session_id}",
            )


def _get_title(entry: dict | ArchitectureModel) -> str:
    """Extract the title from a history entry.

    Supports both dict format (from Generator) and direct ArchitectureModel.

    Args:
        entry: A history entry, either a dict or ArchitectureModel.

    Returns:
        The architecture title string.
    """
    if isinstance(entry, dict):
        arch = entry.get("architecture")
        if isinstance(arch, ArchitectureModel):
            return arch.title
        return str(arch) if arch else "Untitled"
    if isinstance(entry, ArchitectureModel):
        return entry.title
    return "Untitled"


def _get_architecture(entry: dict | ArchitectureModel) -> ArchitectureModel:
    """Extract the ArchitectureModel from a history entry.

    Supports both dict format (from Generator) and direct ArchitectureModel.

    Args:
        entry: A history entry, either a dict or ArchitectureModel.

    Returns:
        The ArchitectureModel instance.
    """
    if isinstance(entry, dict):
        return entry["architecture"]
    return entry


def _display_architecture(architecture: ArchitectureModel) -> None:
    """Display an architecture in the standard tabbed format.

    Args:
        architecture: The ArchitectureModel instance to display.
    """
    st.header(architecture.title)

    tabs = st.tabs(
        ["Overview", "Diagram", "AWS Services", "Security", "Cost", "Exports"]
    )

    # Overview tab
    with tabs[0]:
        st.subheader("Summary")
        st.write(architecture.summary)
        st.subheader("Architecture Description")
        st.write(architecture.architecture_description)
        if architecture.recommendations:
            st.subheader("Recommendations")
            for rec in architecture.recommendations:
                st.markdown(f"- {rec}")

    # Diagram tab
    with tabs[1]:
        nodes = architecture.diagram.nodes
        connections = architecture.diagram.connections

        if not nodes:
            st.info("No diagram data available for this architecture.")
        else:
            diagram_mode = st.radio(
                "Visualization Mode",
                options=["Mermaid", "Draw.io"],
                index=0,
                key=f"history_diagram_mode_{architecture.title}",
            )

            if diagram_mode == "Mermaid":
                mermaid_code = to_mermaid(nodes, connections)
                if mermaid_code:
                    st.code(mermaid_code, language="mermaid")
                else:
                    st.info("No Mermaid diagram available.")
            else:
                drawio_xml = to_drawio_xml(nodes, connections)
                if drawio_xml:
                    st.text_area(
                        "Draw.io XML",
                        value=drawio_xml,
                        height=300,
                        key=f"history_drawio_xml_{architecture.title}",
                    )
                    st.download_button(
                        label="Download Draw.io XML",
                        data=drawio_xml,
                        file_name=generate_export_filename(
                            architecture.title, "drawio", "drawio"
                        ),
                        mime="application/xml",
                        key=f"history_drawio_download_{architecture.title}",
                    )
                else:
                    st.info("No Draw.io diagram available.")

    # AWS Services tab
    with tabs[2]:
        if not architecture.aws_services:
            st.info("No AWS services data available for this architecture.")
        else:
            for service in architecture.aws_services:
                st.markdown(f"**{service.name}** — {service.role}")

    # Security tab
    with tabs[3]:
        security = architecture.security
        has_security_data = (
            security.iam_policies
            or security.encryption
            or security.cloudtrail
            or security.waf_rules
            or security.recommendations
        )

        if not has_security_data:
            st.info("No security data available for this architecture.")
        else:
            if security.iam_policies:
                st.subheader("IAM Policies")
                for policy in security.iam_policies:
                    st.markdown(f"- {policy}")
            if security.encryption:
                st.subheader("Encryption")
                for item in security.encryption:
                    st.markdown(f"- {item}")
            if security.cloudtrail:
                st.subheader("CloudTrail")
                for item in security.cloudtrail:
                    st.markdown(f"- {item}")
            if security.waf_rules:
                st.subheader("WAF Rules")
                for rule in security.waf_rules:
                    st.markdown(f"- {rule}")
            if security.recommendations:
                st.subheader("Security Recommendations")
                for rec in security.recommendations:
                    st.markdown(f"- {rec}")

    # Cost tab
    with tabs[4]:
        cost = architecture.estimated_cost
        if not cost.total_monthly and not cost.breakdown:
            st.info("No cost data available for this architecture.")
        else:
            cost_summary = format_cost_summary(cost)
            st.metric("Estimated Monthly Cost", cost_summary.total_monthly)
            if cost_summary.services:
                st.subheader("Per-Service Breakdown")
                for svc in cost_summary.services:
                    st.markdown(f"- **{svc.service}**: {svc.monthly_cost}")

    # Exports tab
    with tabs[5]:
        nodes = architecture.diagram.nodes
        connections = architecture.diagram.connections

        # JSON export
        json_data = architecture.model_dump_json(indent=2)
        st.download_button(
            label="Download Architecture JSON",
            data=json_data,
            file_name=generate_export_filename(
                architecture.title, "architecture", "json"
            ),
            mime="application/json",
            key=f"history_json_export_{architecture.title}",
        )

        # Mermaid export
        if nodes:
            mermaid_code = to_mermaid(nodes, connections)
            if mermaid_code:
                st.download_button(
                    label="Download Mermaid (.mmd)",
                    data=mermaid_code,
                    file_name=generate_export_filename(
                        architecture.title, "mermaid", "mmd"
                    ),
                    mime="text/plain",
                    key=f"history_mermaid_export_{architecture.title}",
                )

        # Draw.io export
        if nodes:
            drawio_xml = to_drawio_xml(nodes, connections)
            if drawio_xml:
                st.download_button(
                    label="Download Draw.io (.drawio)",
                    data=drawio_xml,
                    file_name=generate_export_filename(
                        architecture.title, "drawio", "drawio"
                    ),
                    mime="application/xml",
                    key=f"history_drawio_export_{architecture.title}",
                )


# Run the page
render_history_page()
