"""Diagram Agent module.

Implements the DiagramAgent that generates professional AWS architecture diagrams
via the Draw.io MCP server or falls back to local XML rendering.

Responsibilities:
- Generate Draw.io XML with AWS icon stencils, VPC boundaries, AZ layouts
- Fall back to local XML generation when MCP unavailable
- Generate PNG rendering for inline display
- Ensure diagram nodes correspond to architecture services
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from models.report import ArchitectureReport
from services.aws_diagram import generate_aws_diagram
from services.diagram import to_drawio_xml

if TYPE_CHECKING:
    from strands.tools.mcp import MCPClient

logger = logging.getLogger(__name__)


class DiagramResult(BaseModel):
    """Result of diagram generation containing Draw.io XML and optional PNG."""

    drawio_xml: str = Field(description="Draw.io mxGraphModel XML content")
    png_bytes: bytes | None = Field(
        default=None, description="PNG rendering bytes for inline display"
    )


class DiagramAgent:
    """Agent that generates professional AWS architecture diagrams.

    Uses the Draw.io MCP server when available to produce diagrams with official
    AWS icon stencils, VPC boundaries, and availability zone layouts. Falls back
    to local XML generation and PNG rendering when MCP is unavailable.
    """

    def __init__(
        self,
        drawio_mcp: "MCPClient | None" = None,
        model: str | None = None,
    ) -> None:
        """Initialize the DiagramAgent.

        Args:
            drawio_mcp: Optional MCP client for Draw.io diagram generation.
                If None or connection fails, falls back to local rendering.
            model: Optional model identifier for the Strands agent (unused in
                fallback mode, reserved for future MCP-driven generation).
        """
        self.drawio_mcp = drawio_mcp
        self.model = model

    def generate(self, report: ArchitectureReport) -> DiagramResult:
        """Generate Draw.io diagram from an architecture report.

        Attempts to use the Draw.io MCP server for professional diagram
        generation with AWS icon stencils. If MCP is unavailable or fails,
        falls back to local XML generation and PNG rendering.

        Args:
            report: The architecture report containing services and topology.

        Returns:
            DiagramResult with Draw.io XML and optional PNG bytes.
        """
        # Attempt MCP-based generation first
        if self.drawio_mcp is not None:
            try:
                result = self._generate_via_mcp(report)
                if result is not None:
                    return result
            except Exception as exc:
                logger.warning(
                    "Draw.io MCP generation failed, falling back to local: %s", exc
                )

        # Fallback to local generation
        return self._generate_local(report)

    def _generate_via_mcp(self, report: ArchitectureReport) -> DiagramResult | None:
        """Generate diagram using the Draw.io MCP server.

        Builds a prompt describing the architecture and sends it to the MCP
        server's diagram generation tool.

        Args:
            report: The architecture report.

        Returns:
            DiagramResult if MCP generation succeeds, None otherwise.
        """
        if self.drawio_mcp is None:
            return None

        try:
            # Build a description of the architecture for MCP tool input
            services_desc = ", ".join(
                f"{svc.name} ({svc.role})" for svc in report.aws_services
            )
            connections_desc = "; ".join(
                f"{conn.source_id} -> {conn.target_id}"
                + (f" ({conn.label})" if conn.label else "")
                for conn in report.diagram.connections
            )

            diagram_prompt = (
                f"Generate an AWS architecture diagram for: {report.title}. "
                f"Services: {services_desc}. "
                f"Connections: {connections_desc}. "
                f"Include VPC boundaries and availability zone layouts. "
                f"Use official AWS icon stencils."
            )

            # Invoke the MCP tool for diagram generation
            from strands import Agent

            agent = Agent(
                tools=[self.drawio_mcp],
                model=self.model or "us.anthropic.claude-sonnet-4-20250514",
            )
            result = agent(diagram_prompt)

            # Extract XML from the agent response
            response_text = str(result)

            # Look for mxGraphModel XML in the response
            xml_start = response_text.find("<mxGraphModel")
            xml_end = response_text.find("</mxGraphModel>")

            if xml_start != -1 and xml_end != -1:
                drawio_xml = response_text[xml_start : xml_end + len("</mxGraphModel>")]
                # Generate PNG from local service using the nodes/connections
                png_bytes = generate_aws_diagram(
                    nodes=report.diagram.nodes,
                    connections=report.diagram.connections,
                    title=report.title,
                )
                return DiagramResult(drawio_xml=drawio_xml, png_bytes=png_bytes)

            logger.warning("MCP response did not contain valid Draw.io XML")
            return None

        except ImportError as exc:
            logger.warning("Strands SDK not available for MCP generation: %s", exc)
            return None
        except Exception as exc:
            logger.warning("MCP diagram generation failed: %s", exc)
            return None

    def _generate_local(self, report: ArchitectureReport) -> DiagramResult:
        """Generate diagram using local services (fallback path).

        Uses the existing diagram services:
        - services.diagram.to_drawio_xml() for Draw.io XML
        - services.aws_diagram.generate_aws_diagram() for PNG rendering

        Args:
            report: The architecture report.

        Returns:
            DiagramResult with locally generated XML and PNG.
        """
        nodes = report.diagram.nodes
        connections = report.diagram.connections

        # Generate Draw.io XML using existing service
        drawio_xml = to_drawio_xml(nodes=nodes, connections=connections)

        # Generate PNG using existing AWS diagram service
        png_bytes = generate_aws_diagram(
            nodes=nodes,
            connections=connections,
            title=report.title,
        )

        return DiagramResult(drawio_xml=drawio_xml, png_bytes=png_bytes)
