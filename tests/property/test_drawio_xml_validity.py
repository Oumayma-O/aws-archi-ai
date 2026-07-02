# Feature: aws-architect-ai, Property 6: Draw.io XML generation produces well-formed XML
"""
Property-based test: For any list of DiagramNode objects and list of
DiagramConnection objects (where all connection source_id and target_id values
reference existing node ids), the to_drawio_xml function SHALL produce
well-formed XML that parses without error and contains an mxGraphModel root
element, one mxCell element per node, and one mxCell edge element per connection.

**Validates: Requirements 5.2, 13.3**
"""

import xml.etree.ElementTree as ET

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from models.architecture import DiagramConnection, DiagramNode
from services.diagram import to_drawio_xml


# Strategy: generate unique alphanumeric node IDs
node_id_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        min_codepoint=48,
        max_codepoint=122,
    ),
    min_size=1,
    max_size=10,
).filter(lambda s: s.isalnum())


# Strategy: generate a list of DiagramNode with unique IDs
@st.composite
def diagram_nodes_strategy(draw: st.DrawFn) -> list[DiagramNode]:
    """Generate a list of DiagramNode objects with unique IDs."""
    num_nodes = draw(st.integers(min_value=1, max_value=8))
    ids: list[str] = []
    for _ in range(num_nodes):
        node_id = draw(node_id_strategy.filter(lambda x, seen=ids: x not in seen))
        ids.append(node_id)

    nodes = []
    for node_id in ids:
        label = draw(
            st.text(
                alphabet=st.characters(
                    whitelist_categories=("L", "N", "P", "Z"),
                    min_codepoint=32,
                    max_codepoint=126,
                ),
                min_size=1,
                max_size=20,
            )
        )
        aws_service = draw(
            st.sampled_from(
                ["EC2", "S3", "Lambda", "RDS", "DynamoDB", "SQS", "SNS", "ECS"]
            )
        )
        nodes.append(
            DiagramNode(id=node_id, label=label, aws_service=aws_service)
        )
    return nodes


# Strategy: generate printable text for labels (XML-safe characters)
printable_label_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        min_codepoint=32,
        max_codepoint=126,
    ),
    min_size=1,
    max_size=15,
)


@st.composite
def diagram_with_connections(
    draw: st.DrawFn,
) -> tuple[list[DiagramNode], list[DiagramConnection]]:
    """Generate nodes and connections where all connections reference valid node IDs."""
    nodes = draw(diagram_nodes_strategy())
    node_ids = [n.id for n in nodes]

    num_connections = draw(st.integers(min_value=0, max_value=min(len(node_ids) * 2, 10)))
    connections: list[DiagramConnection] = []

    for _ in range(num_connections):
        source_id = draw(st.sampled_from(node_ids))
        target_id = draw(st.sampled_from(node_ids))
        label = draw(st.one_of(st.none(), printable_label_strategy))
        connections.append(
            DiagramConnection(source_id=source_id, target_id=target_id, label=label)
        )

    return nodes, connections


@given(data=diagram_with_connections())
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_drawio_xml_well_formed_with_correct_counts(
    data: tuple[list[DiagramNode], list[DiagramConnection]],
) -> None:
    """
    Property 6: Draw.io XML generation produces well-formed XML.

    For any list of DiagramNode objects and list of DiagramConnection objects
    (where all connection source_id and target_id values reference existing
    node ids), the to_drawio_xml function SHALL produce well-formed XML that
    parses without error and contains an mxGraphModel root element, one mxCell
    element per node, and one mxCell edge element per connection.

    **Validates: Requirements 5.2, 13.3**
    """
    nodes, connections = data

    xml_output = to_drawio_xml(nodes, connections)

    # Output must be non-empty since we generate at least 1 node
    assert xml_output, "to_drawio_xml returned empty string for non-empty nodes list"

    # Must parse as well-formed XML
    try:
        root = ET.fromstring(xml_output)
    except ET.ParseError as e:
        raise AssertionError(
            f"to_drawio_xml produced invalid XML: {e}\nOutput:\n{xml_output}"
        )

    # Root element must be mxGraphModel
    assert root.tag == "mxGraphModel", (
        f"Expected root element 'mxGraphModel', got '{root.tag}'"
    )

    # Find all mxCell elements
    root_elem = root.find("root")
    assert root_elem is not None, "mxGraphModel must contain a <root> element"

    all_cells = root_elem.findall("mxCell")

    # Count vertex cells (nodes) - those with vertex="1"
    vertex_cells = [c for c in all_cells if c.get("vertex") == "1"]
    # Count edge cells (connections) - those with edge="1"
    edge_cells = [c for c in all_cells if c.get("edge") == "1"]

    # Vertex count must equal number of nodes
    assert len(vertex_cells) == len(nodes), (
        f"Expected {len(nodes)} vertex mxCell elements, got {len(vertex_cells)}"
    )

    # Edge count must equal number of connections
    assert len(edge_cells) == len(connections), (
        f"Expected {len(connections)} edge mxCell elements, got {len(edge_cells)}"
    )
