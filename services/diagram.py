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


# Zone classification for container boxes. VPC-resident services get their
# own column band so the VPC boundary box can never overlap non-members.
_VPC_KEYWORDS = (
    "ecs", "fargate", "ec2", "eks", "rds", "aurora", "elasticache", "redis",
    "efs", "alb", "elb", "load balancer", "postgres", "mysql", "vpc",
)
_EXTERNAL_KEYWORDS = (
    "user", "client", "external", "internet", "browser", "mobile",
    "stripe", "paypal", "square", "github", "third-party", "third party",
)

_GROUP_STYLE_BASE = (
    "points=[[0,0],[0.25,0],[0.5,0],[0.75,0],[1,0],[1,0.25],[1,0.5],[1,0.75],"
    "[1,1],[0.75,1],[0.5,1],[0.25,1],[0,1],[0,0.75],[0,0.5],[0,0.25]];"
    "outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;fontSize=12;"
    "fontStyle=0;container=1;pointerEvents=0;collapsible=0;recursiveResize=0;"
    "shape=mxgraph.aws4.group;verticalAlign=top;align=left;spacingLeft=30;dashed=0;"
)
_AWS_CLOUD_GROUP_STYLE = (
    _GROUP_STYLE_BASE
    + "grIcon=mxgraph.aws4.group_aws_cloud_alt;strokeColor=#232F3E;fillColor=none;fontColor=#232F3E;"
)
_VPC_GROUP_STYLE = (
    _GROUP_STYLE_BASE
    + "grIcon=mxgraph.aws4.group_vpc2;strokeColor=#8C4FFF;fillColor=none;fontColor=#8C4FFF;"
)


def _node_zone(node: DiagramNode) -> str:
    """Resolve a node's boundary zone: 'external', 'vpc', or 'cloud'.

    The design agent declares placement on each node (DiagramNode.zone) —
    the model knows what it put in the VPC, so rendering honors its intent.
    Keyword inference remains only as the fallback for nodes without a
    declared zone (legacy reports, hand-built diagrams).
    """
    declared = (node.zone or "").strip().lower()
    if declared in ("external", "vpc", "cloud"):
        return declared

    haystack = f"{node.aws_service} {node.label}".lower()
    if any(kw in haystack for kw in _EXTERNAL_KEYWORDS):
        return "external"
    if any(kw in haystack for kw in _VPC_KEYWORDS):
        return "vpc"
    return "cloud"


def _layered_positions(
    nodes: list[DiagramNode], connections: list[DiagramConnection]
) -> tuple[dict[str, tuple[int, int]], dict[str, str]]:
    """Assign top-down layered positions via BFS from in-degree-0 roots.

    Mirrors the request flow of the PNG renderer: sources (Users, Route 53)
    on top, data stores and monitoring toward the bottom. Within each row,
    external + cloud nodes occupy the left band and VPC-resident nodes an
    exclusive right band, so the VPC container box encloses only members.

    Returns (positions, zone-by-node-id).
    """
    node_ids = [n.id for n in nodes]
    id_set = set(node_ids)
    zones = {n.id: _node_zone(n) for n in nodes}

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

    x_spacing, y_spacing = 220, 170
    left_x0, top_y0 = 80, 100

    # Width of the left band = widest external+cloud row; the VPC band
    # starts strictly to its right.
    widest_left = max(
        (len([n for n in members if zones[n] != "vpc"]) for members in layers.values()),
        default=0,
    )
    vpc_x0 = left_x0 + max(widest_left, 1) * x_spacing + 60

    positions: dict[str, tuple[int, int]] = {}
    for layer, members in sorted(layers.items()):
        y = top_y0 + layer * y_spacing
        li = vi = 0
        for nid in members:
            if zones[nid] == "vpc":
                positions[nid] = (vpc_x0 + vi * x_spacing, y)
                vi += 1
            else:
                positions[nid] = (left_x0 + li * x_spacing, y)
                li += 1
    return positions, zones


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
    positions, zones = _layered_positions(nodes, connections)
    icon = 78
    pad_side, pad_top, pad_bottom = 30, 45, 55  # room for group labels + node labels

    def _bbox(ids: list[str]) -> tuple[int, int, int, int]:
        xs = [positions[i][0] for i in ids]
        ys = [positions[i][1] for i in ids]
        x0 = min(xs) - pad_side
        y0 = min(ys) - pad_top
        x1 = max(xs) + icon + pad_side
        y1 = max(ys) + icon + pad_bottom
        return x0, y0, x1 - x0, y1 - y0

    cloud_members = [n.id for n in nodes if zones[n.id] == "cloud"]
    vpc_members = [n.id for n in nodes if zones[n.id] == "vpc"]

    # Build XML structure
    root = ET.Element("mxGraphModel")
    root_cell = ET.SubElement(root, "root")

    # Default parent cells required by Draw.io
    ET.SubElement(root_cell, "mxCell", id="0")
    ET.SubElement(root_cell, "mxCell", id="1", parent="0")

    def _emit_group(gid: str, label: str, style: str, parent: str,
                    box: tuple[int, int, int, int], origin: tuple[int, int]) -> None:
        cell = ET.SubElement(
            root_cell, "mxCell",
            id=gid, value=label, style=style, vertex="1", parent=parent,
        )
        ET.SubElement(
            cell, "mxGeometry",
            x=str(box[0] - origin[0]), y=str(box[1] - origin[1]),
            width=str(box[2]), height=str(box[3]),
        ).set("as", "geometry")

    # Containers: AWS Cloud boundary around every AWS node; a VPC box (nested
    # inside it) around VPC-resident services. Skipped when empty — a page of
    # purely external nodes gets no boxes.
    cloud_origin = vpc_origin = (0, 0)
    have_cloud = bool(cloud_members or vpc_members)
    if have_cloud:
        cloud_box = _bbox(cloud_members + vpc_members)
        if vpc_members:
            # Grow the cloud box so the nested VPC box keeps its padding
            vpc_box = _bbox(vpc_members)
            x0 = min(cloud_box[0], vpc_box[0] - pad_side)
            y0 = min(cloud_box[1], vpc_box[1] - pad_top)
            x1 = max(cloud_box[0] + cloud_box[2], vpc_box[0] + vpc_box[2] + pad_side)
            y1 = max(cloud_box[1] + cloud_box[3], vpc_box[1] + vpc_box[3] + pad_bottom)
            cloud_box = (x0, y0, x1 - x0, y1 - y0)
        _emit_group("group_aws_cloud", "AWS Cloud", _AWS_CLOUD_GROUP_STYLE, "1",
                    cloud_box, (0, 0))
        cloud_origin = (cloud_box[0], cloud_box[1])
        if vpc_members:
            _emit_group("group_vpc", "VPC", _VPC_GROUP_STYLE, "group_aws_cloud",
                        vpc_box, cloud_origin)
            vpc_origin = (vpc_box[0], vpc_box[1])

    for node in nodes:
        x, y = positions[node.id]
        zone = zones[node.id]
        if zone == "vpc":
            parent, origin = "group_vpc", vpc_origin
        elif zone == "cloud":
            parent, origin = "group_aws_cloud", cloud_origin
        else:
            parent, origin = "1", (0, 0)
        cell = ET.SubElement(
            root_cell,
            "mxCell",
            id=node.id,
            value=node.label,
            style=_drawio_node_style(node),
            vertex="1",
            parent=parent,
        )
        ET.SubElement(
            cell,
            "mxGeometry",
            x=str(x - origin[0]),
            y=str(y - origin[1]),
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
