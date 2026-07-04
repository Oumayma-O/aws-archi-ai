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


# draw.io AWS 2017+ shape library (mxgraph.aws4) — bundled in app.diagrams.net.
# Maps a lowercase keyword found in aws_service to (resIcon suffix, category color).
# Category colors follow the official AWS architecture-icon palette.
_AWS4_ICONS: list[tuple[str, str, str]] = [
    ("lambda", "lambda", "#ED7100"),
    ("fargate", "fargate", "#ED7100"),
    ("ecs", "elastic_container_service", "#ED7100"),
    ("eks", "elastic_kubernetes_service", "#ED7100"),
    ("ec2", "ec2", "#ED7100"),
    ("api gateway", "api_gateway", "#E7157B"),
    ("apigateway", "api_gateway", "#E7157B"),
    ("dynamodb", "dynamodb", "#C925D1"),
    ("aurora", "aurora", "#C925D1"),
    ("rds", "rds", "#C925D1"),
    ("elasticache", "elasticache", "#C925D1"),
    ("s3", "s3", "#7AA116"),
    ("efs", "elastic_file_system", "#7AA116"),
    ("cloudfront", "cloudfront", "#8C4FFF"),
    ("route 53", "route_53", "#8C4FFF"),
    ("route53", "route_53", "#8C4FFF"),
    ("elb", "elastic_load_balancing", "#8C4FFF"),
    ("alb", "elastic_load_balancing", "#8C4FFF"),
    ("load balancer", "elastic_load_balancing", "#8C4FFF"),
    ("vpc", "vpc", "#8C4FFF"),
    ("waf", "waf", "#DD344C"),
    ("cognito", "cognito", "#DD344C"),
    ("iam", "identity_and_access_management", "#DD344C"),
    ("kms", "key_management_service", "#DD344C"),
    ("secrets manager", "secrets_manager", "#DD344C"),
    ("secretsmanager", "secrets_manager", "#DD344C"),
    ("shield", "shield", "#DD344C"),
    ("cloudwatch", "cloudwatch", "#E7157B"),
    ("cloudtrail", "cloudtrail", "#E7157B"),
    ("x-ray", "xray", "#E7157B"),
    ("xray", "xray", "#E7157B"),
    ("sns", "simple_notification_service", "#E7157B"),
    ("sqs", "simple_queue_service", "#E7157B"),
    ("eventbridge", "eventbridge", "#E7157B"),
    ("step functions", "step_functions", "#E7157B"),
    ("kinesis", "kinesis", "#8C4FFF"),
    ("athena", "athena", "#8C4FFF"),
    ("glue", "glue", "#8C4FFF"),
    ("sagemaker", "sagemaker", "#01A88D"),
    ("bedrock", "bedrock", "#01A88D"),
    ("amplify", "amplify", "#DD344C"),
]

_AWS4_RESOURCE_STYLE = (
    "sketch=0;points=[[0,0,0],[0.25,0,0],[0.5,0,0],[0.75,0,0],[1,0,0],"
    "[0,1,0],[0.25,1,0],[0.5,1,0],[0.75,1,0],[1,1,0],[0,0.25,0],[0,0.5,0],"
    "[0,0.75,0],[1,0.25,0],[1,0.5,0],[1,0.75,0]];"
    "outlineConnect=0;fontColor=#232F3E;gradientColor=none;fillColor={color};"
    "strokeColor=#ffffff;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;"
    "align=center;html=1;fontSize=12;fontStyle=0;aspect=fixed;"
    "shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{icon};"
)

_AWS4_USERS_STYLE = (
    "sketch=0;outlineConnect=0;fontColor=#232F3E;gradientColor=none;"
    "fillColor=#232F3E;strokeColor=none;dashed=0;verticalLabelPosition=bottom;"
    "verticalAlign=top;align=center;html=1;shape=mxgraph.aws4.users;"
)

_DRAWIO_EDGE_STYLE = (
    "edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;fontSize=10;"
    "labelBackgroundColor=#FFFFFF;strokeColor=#545B64;jettySize=auto;"
    "orthogonalLoop=1;"
)


def _drawio_node_style(node: DiagramNode) -> str:
    """Pick the AWS shape style for a node."""
    haystack = f"{node.aws_service} {node.label}".lower()
    if "user" in haystack or "client" in haystack or "external" in haystack:
        return _AWS4_USERS_STYLE
    for keyword, icon, color in _AWS4_ICONS:
        if keyword in haystack:
            return _AWS4_RESOURCE_STYLE.format(color=color, icon=icon)
    # Unknown service: generic AWS resource card in the service's brand color
    return (
        f"rounded=1;whiteSpace=wrap;html=1;fillColor={_get_service_color(node.aws_service)};"
        "fontColor=#ffffff;strokeColor=none;fontSize=12;"
    )


def _layered_positions(
    nodes: list[DiagramNode], connections: list[DiagramConnection]
) -> dict[str, tuple[int, int]]:
    """Assign top-down layered positions via BFS from in-degree-0 roots.

    Mirrors the request flow of the PNG renderer: sources (Users, Route 53)
    on top, data stores and monitoring toward the bottom. Prevents the
    label-soup that a naive grid produces in the draw.io editor.
    """
    node_ids = [n.id for n in nodes]
    id_set = set(node_ids)
    adjacency: dict[str, list[str]] = {nid: [] for nid in node_ids}
    in_degree: dict[str, int] = {nid: 0 for nid in node_ids}
    for conn in connections:
        if conn.source_id in id_set and conn.target_id in id_set:
            adjacency[conn.source_id].append(conn.target_id)
            in_degree[conn.target_id] += 1

    roots = [nid for nid in node_ids if in_degree[nid] == 0] or node_ids[:1]

    layer_of: dict[str, int] = {}
    frontier = list(roots)
    depth = 0
    while frontier:
        next_frontier: list[str] = []
        for nid in frontier:
            if nid in layer_of:
                continue
            layer_of[nid] = depth
            next_frontier.extend(adjacency[nid])
        frontier = next_frontier
        depth += 1

    # Anything unreached (cycles, orphans) goes below the deepest layer
    max_layer = max(layer_of.values(), default=0)
    for nid in node_ids:
        layer_of.setdefault(nid, max_layer + 1)

    layers: dict[int, list[str]] = {}
    for nid in node_ids:  # preserve node order within a layer
        layers.setdefault(layer_of[nid], []).append(nid)

    x_spacing, y_spacing, icon_w = 220, 170, 78
    widest = max(len(members) for members in layers.values())
    canvas_center = (widest * x_spacing) // 2 + 60

    positions: dict[str, tuple[int, int]] = {}
    for layer, members in sorted(layers.items()):
        row_width = (len(members) - 1) * x_spacing
        start_x = canvas_center - row_width // 2 - icon_w // 2
        for i, nid in enumerate(members):
            positions[nid] = (start_x + i * x_spacing, 60 + layer * y_spacing)
    return positions


def to_drawio_xml(
    nodes: list[DiagramNode], connections: list[DiagramConnection]
) -> str:
    """Convert nodes and connections to Draw.io mxGraphModel XML.

    Emits official AWS architecture icons (draw.io's bundled mxgraph.aws4
    shape library) laid out top-down by request flow, so the exported
    diagram matches the in-app PNG instead of a grid of generic boxes.
    Connections referencing non-existent node IDs are skipped with a
    warning logged.

    Args:
        nodes: List of diagram nodes.
        connections: List of connections.

    Returns:
        Well-formed Draw.io XML string. Empty string if nodes list is empty.
    """
    if not nodes:
        return ""

    node_ids = {node.id for node in nodes}
    positions = _layered_positions(nodes, connections)

    # Build XML structure
    root = ET.Element("mxGraphModel")
    root_cell = ET.SubElement(root, "root")

    # Default parent cells required by Draw.io
    ET.SubElement(root_cell, "mxCell", id="0")
    ET.SubElement(root_cell, "mxCell", id="1", parent="0")

    for node in nodes:
        x, y = positions[node.id]
        cell = ET.SubElement(
            root_cell,
            "mxCell",
            id=node.id,
            value=node.label,
            style=_drawio_node_style(node),
            vertex="1",
            parent="1",
        )
        ET.SubElement(
            cell,
            "mxGeometry",
            x=str(x),
            y=str(y),
            width="78",
            height="78",
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
            "style": _DRAWIO_EDGE_STYLE,
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
