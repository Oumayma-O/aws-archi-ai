"""Diagram renderer service for AWS Architect AI.

Converts structured architecture nodes and connections into Mermaid flowchart
syntax, Graphviz DOT, and Draw.io mxGraphModel XML. All conversions are
performed locally without LLM calls.
"""

import logging
import re
import xml.etree.ElementTree as ET
from xml.dom import minidom

from models.architecture import DiagramConnection, DiagramNode

logger = logging.getLogger(__name__)

# AWS service color mapping for Graphviz nodes
AWS_SERVICE_COLORS = {
    "EC2": "#FF9900",
    "ECS": "#FF9900",
    "Lambda": "#FF9900",
    "Fargate": "#FF9900",
    "S3": "#3F8624",
    "RDS": "#3B48CC",
    "Aurora": "#3B48CC",
    "DynamoDB": "#3B48CC",
    "ElastiCache": "#3B48CC",
    "CloudFront": "#8C4FFF",
    "Route53": "#8C4FFF",
    "API Gateway": "#FF4F8B",
    "ALB": "#8C4FFF",
    "ELB": "#8C4FFF",
    "VPC": "#8C4FFF",
    "WAF": "#DD344C",
    "IAM": "#DD344C",
    "CloudWatch": "#FF4F8B",
    "SNS": "#FF4F8B",
    "SQS": "#FF4F8B",
    "Cognito": "#DD344C",
    "Secrets Manager": "#DD344C",
    "KMS": "#DD344C",
}


def to_graphviz(
    nodes: list[DiagramNode], connections: list[DiagramConnection]
) -> str:
    """Convert nodes and connections to Graphviz DOT syntax.

    Produces a directed graph with AWS color-coded nodes for use with
    st.graphviz_chart(). Returns empty string for empty node lists.

    Args:
        nodes: List of diagram nodes with id, label, aws_service.
        connections: List of connections with source_id, target_id, optional label.

    Returns:
        Graphviz DOT string.
    """
    if not nodes:
        return ""

    node_ids = {node.id for node in nodes}
    lines = [
        "digraph Architecture {",
        "    rankdir=TB;",
        "    bgcolor=transparent;",
        '    node [shape=box, style="rounded,filled", fontname="Arial", fontsize=11];',
        '    edge [fontname="Arial", fontsize=9, color="#555555"];',
        "",
    ]

    # Node definitions with AWS colors
    for node in nodes:
        color = _get_service_color(node.aws_service)
        label = f"{node.label}\\n({node.aws_service})"
        lines.append(
            f'    {node.id} [label="{label}", fillcolor="{color}", '
            f'fontcolor="white"];'
        )

    lines.append("")

    # Connections
    for conn in connections:
        if conn.source_id not in node_ids or conn.target_id not in node_ids:
            continue
        if conn.label:
            lines.append(
                f'    {conn.source_id} -> {conn.target_id} [label="{conn.label}"];'
            )
        else:
            lines.append(f"    {conn.source_id} -> {conn.target_id};")

    lines.append("}")
    return "\n".join(lines)


def _get_service_color(aws_service: str) -> str:
    """Get AWS brand color for a service type."""
    for key, color in AWS_SERVICE_COLORS.items():
        if key.lower() in aws_service.lower():
            return color
    return "#232F3E"  # AWS dark default


def to_mermaid(
    nodes: list[DiagramNode], connections: list[DiagramConnection]
) -> str:
    """Convert nodes and connections to Mermaid flowchart syntax.

    Produces a Mermaid flowchart with one node definition per node and one
    link statement per connection. Connections referencing non-existent node
    IDs are skipped with a warning logged.

    Args:
        nodes: List of diagram nodes with id, label, aws_service.
        connections: List of connections with source_id, target_id, optional label.

    Returns:
        Mermaid flowchart code string. Empty string if nodes list is empty.
    """
    if not nodes:
        return ""

    node_ids = {node.id for node in nodes}
    lines: list[str] = ["flowchart TD"]

    # Node definitions: node_id["Label (aws_service)"]
    for node in nodes:
        escaped_label = _escape_mermaid_label(f"{node.label} ({node.aws_service})")
        lines.append(f"    {node.id}[\"{escaped_label}\"]")

    # Connection statements
    for conn in connections:
        if conn.source_id not in node_ids:
            logger.warning(
                "Skipping connection: source_id '%s' does not exist in nodes",
                conn.source_id,
            )
            continue
        if conn.target_id not in node_ids:
            logger.warning(
                "Skipping connection: target_id '%s' does not exist in nodes",
                conn.target_id,
            )
            continue

        if conn.label:
            escaped_conn_label = _escape_mermaid_label(conn.label)
            lines.append(
                f"    {conn.source_id} -->|{escaped_conn_label}| {conn.target_id}"
            )
        else:
            lines.append(f"    {conn.source_id} --> {conn.target_id}")

    return "\n".join(lines)


def to_drawio_xml(
    nodes: list[DiagramNode], connections: list[DiagramConnection]
) -> str:
    """Convert nodes and connections to Draw.io mxGraphModel XML.

    Produces well-formed XML with an mxGraphModel root element containing
    one mxCell per node and one mxCell edge per connection. Connections
    referencing non-existent node IDs are skipped with a warning logged.

    Args:
        nodes: List of diagram nodes.
        connections: List of connections.

    Returns:
        Well-formed Draw.io XML string. Empty string if nodes list is empty.
    """
    if not nodes:
        return ""

    node_ids = {node.id for node in nodes}

    # Build XML structure
    root = ET.Element("mxGraphModel")
    root_cell = ET.SubElement(root, "root")

    # Default parent cells required by Draw.io
    ET.SubElement(root_cell, "mxCell", id="0")
    ET.SubElement(root_cell, "mxCell", id="1", parent="0")

    # Node cells
    x_offset = 100
    y_offset = 100
    node_spacing_x = 200
    node_spacing_y = 150
    nodes_per_row = 3

    for i, node in enumerate(nodes):
        row = i // nodes_per_row
        col = i % nodes_per_row
        x = x_offset + col * node_spacing_x
        y = y_offset + row * node_spacing_y

        cell = ET.SubElement(
            root_cell,
            "mxCell",
            id=node.id,
            value=f"{node.label} ({node.aws_service})",
            style="rounded=1;whiteSpace=wrap;html=1;",
            vertex="1",
            parent="1",
        )
        ET.SubElement(
            cell,
            "mxGeometry",
            x=str(x),
            y=str(y),
            width="160",
            height="60",
        ).set("as", "geometry")

    # Edge cells
    edge_counter = 0
    for conn in connections:
        if conn.source_id not in node_ids:
            logger.warning(
                "Skipping connection: source_id '%s' does not exist in nodes",
                conn.source_id,
            )
            continue
        if conn.target_id not in node_ids:
            logger.warning(
                "Skipping connection: target_id '%s' does not exist in nodes",
                conn.target_id,
            )
            continue

        edge_id = f"edge_{edge_counter}"
        edge_counter += 1

        edge_attrs: dict[str, str] = {
            "id": edge_id,
            "style": "edgeStyle=orthogonalEdgeStyle;",
            "edge": "1",
            "source": conn.source_id,
            "target": conn.target_id,
            "parent": "1",
        }
        if conn.label:
            edge_attrs["value"] = conn.label

        edge_cell = ET.SubElement(root_cell, "mxCell", **edge_attrs)
        ET.SubElement(edge_cell, "mxGeometry", relative="1").set("as", "geometry")

    # Produce formatted XML
    rough_string = ET.tostring(root, encoding="unicode", xml_declaration=False)
    dom = minidom.parseString(rough_string)
    return dom.toprettyxml(indent="  ", encoding=None).replace(
        '<?xml version="1.0" ?>\n', ""
    ).strip()


def parse_mermaid(
    mermaid_code: str,
) -> tuple[list[DiagramNode], list[DiagramConnection]]:
    """Parse Mermaid flowchart code back into nodes and connections.

    Extracts node definitions and connection statements from Mermaid
    flowchart syntax for round-trip verification.

    Args:
        mermaid_code: Mermaid flowchart syntax string.

    Returns:
        Tuple of (nodes, connections) extracted from the Mermaid code.
        Returns empty lists if input is empty.
    """
    if not mermaid_code.strip():
        return [], []

    nodes: list[DiagramNode] = []
    connections: list[DiagramConnection] = []
    seen_node_ids: set[str] = set()

    lines = mermaid_code.strip().split("\n")

    for line in lines:
        stripped = line.strip()

        # Skip the flowchart directive line
        if stripped.startswith("flowchart") or stripped.startswith("graph"):
            continue

        # Try to parse as a connection first (connections also define nodes implicitly)
        conn_match = _parse_connection_line(stripped)
        if conn_match:
            connections.append(conn_match)
            continue

        # Try to parse as a node definition
        node_match = _parse_node_definition(stripped)
        if node_match and node_match.id not in seen_node_ids:
            nodes.append(node_match)
            seen_node_ids.add(node_match.id)

    return nodes, connections


def _escape_mermaid_label(text: str) -> str:
    """Escape special characters in Mermaid labels.

    Args:
        text: Raw label text.

    Returns:
        Escaped label safe for Mermaid syntax.
    """
    # Escape quotes within labels
    return text.replace('"', '#quot;')


def _parse_node_definition(line: str) -> DiagramNode | None:
    """Parse a single Mermaid node definition line.

    Expected format: node_id["Label (aws_service)"]

    Args:
        line: A single line from Mermaid code.

    Returns:
        DiagramNode if parsing succeeds, None otherwise.
    """
    # Match: node_id["Label (aws_service)"]
    match = re.match(r'^(\w+)\["(.+)"\]$', line)
    if not match:
        return None

    node_id = match.group(1)
    content = match.group(2)

    # Unescape quotes
    content = content.replace('#quot;', '"')

    # Extract label and aws_service from "Label (aws_service)" format
    label_match = re.match(r'^(.+)\s+\(([^)]+)\)$', content)
    if label_match:
        label = label_match.group(1)
        aws_service = label_match.group(2)
    else:
        # Fallback: use entire content as label
        label = content
        aws_service = ""

    return DiagramNode(id=node_id, label=label, aws_service=aws_service)


def _parse_connection_line(line: str) -> DiagramConnection | None:
    """Parse a single Mermaid connection line.

    Expected formats:
        source_id --> target_id
        source_id -->|label| target_id

    Args:
        line: A single line from Mermaid code.

    Returns:
        DiagramConnection if parsing succeeds, None otherwise.
    """
    # Match: source_id -->|label| target_id
    labeled_match = re.match(r'^(\w+)\s+-->\|(.+?)\|\s+(\w+)$', line)
    if labeled_match:
        return DiagramConnection(
            source_id=labeled_match.group(1),
            target_id=labeled_match.group(3),
            label=labeled_match.group(2).replace('#quot;', '"'),
        )

    # Match: source_id --> target_id
    simple_match = re.match(r'^(\w+)\s+-->\s+(\w+)$', line)
    if simple_match:
        return DiagramConnection(
            source_id=simple_match.group(1),
            target_id=simple_match.group(2),
            label=None,
        )

    return None
