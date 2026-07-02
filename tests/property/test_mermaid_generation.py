# Feature: aws-architect-ai, Property 5: Mermaid generation produces parseable syntax
"""
Property-based test: For any list of DiagramNode objects and list of
DiagramConnection objects (where all connection source_id and target_id values
reference existing node ids), the to_mermaid function SHALL produce a string
that is parseable as valid Mermaid flowchart syntax (containing the flowchart
directive, one node definition per node, and one link statement per connection).

**Validates: Requirements 5.1, 13.2**
"""

from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st

from models.architecture import DiagramConnection, DiagramNode
from services.diagram import to_mermaid


# Strategy: generate alphanumeric node IDs (valid Mermaid identifiers)
node_id_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        min_codepoint=65,
        max_codepoint=122,
    ),
    min_size=1,
    max_size=10,
).filter(lambda s: s.isalnum() and s[0].isalpha())

# Strategy: generate labels and service names (printable, no quotes or parens that break format)
label_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "Zs"),
        min_codepoint=32,
        max_codepoint=126,
    ),
    min_size=1,
    max_size=20,
).filter(lambda s: s.strip() != "" and "(" not in s and ")" not in s and '"' not in s)

aws_service_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        min_codepoint=48,
        max_codepoint=122,
    ),
    min_size=1,
    max_size=15,
).filter(lambda s: s.isalnum())


@st.composite
def diagram_nodes_strategy(draw: st.DrawFn) -> list[DiagramNode]:
    """Generate a list of DiagramNode objects with unique IDs."""
    num_nodes = draw(st.integers(min_value=1, max_value=8))
    ids = draw(
        st.lists(
            node_id_strategy,
            min_size=num_nodes,
            max_size=num_nodes,
            unique=True,
        )
    )
    nodes = []
    for node_id in ids:
        label = draw(label_strategy)
        aws_service = draw(aws_service_strategy)
        nodes.append(
            DiagramNode(id=node_id, label=label, aws_service=aws_service)
        )
    return nodes


@st.composite
def diagram_with_connections_strategy(
    draw: st.DrawFn,
) -> tuple[list[DiagramNode], list[DiagramConnection]]:
    """Generate nodes and connections where all connections reference valid node IDs."""
    nodes = draw(diagram_nodes_strategy())
    node_ids = [n.id for n in nodes]

    num_connections = draw(st.integers(min_value=0, max_value=min(10, len(node_ids) * 2)))
    connections = []
    for _ in range(num_connections):
        source_id = draw(st.sampled_from(node_ids))
        target_id = draw(st.sampled_from(node_ids))
        has_label = draw(st.booleans())
        label = draw(label_strategy) if has_label else None
        connections.append(
            DiagramConnection(source_id=source_id, target_id=target_id, label=label)
        )
    return nodes, connections


@given(data=diagram_with_connections_strategy())
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_mermaid_generation_produces_parseable_syntax(
    data: tuple[list[DiagramNode], list[DiagramConnection]],
) -> None:
    """
    Property 5: Mermaid generation produces parseable syntax.

    For any list of DiagramNode objects and list of DiagramConnection objects
    (where all connection source_id and target_id values reference existing node
    ids), the to_mermaid function SHALL produce a string that is parseable as
    valid Mermaid flowchart syntax (containing the flowchart directive, one node
    definition per node, and one link statement per connection).

    **Validates: Requirements 5.1, 13.2**
    """
    nodes, connections = data

    result = to_mermaid(nodes, connections)

    # Result must not be empty since we always have at least one node
    assert result != "", "to_mermaid returned empty string for non-empty node list"

    lines = result.strip().split("\n")

    # 1. Output starts with "flowchart TD"
    assert lines[0].strip() == "flowchart TD", (
        f"Expected output to start with 'flowchart TD', got: {lines[0]!r}"
    )

    # 2. Contains one node definition per node
    node_ids = {node.id for node in nodes}
    node_definition_lines = [
        line.strip()
        for line in lines[1:]
        if "[" in line and "]" in line and "-->" not in line
    ]
    defined_ids = set()
    for line in node_definition_lines:
        # Extract the node ID (everything before the first '[')
        node_id = line.split("[")[0].strip()
        defined_ids.add(node_id)

    assert defined_ids == node_ids, (
        f"Node definitions mismatch.\n"
        f"Expected node IDs: {node_ids}\n"
        f"Found node IDs: {defined_ids}"
    )

    # 3. Contains one link statement per connection
    link_lines = [
        line.strip() for line in lines[1:] if "-->" in line
    ]
    assert len(link_lines) == len(connections), (
        f"Expected {len(connections)} link statements, found {len(link_lines)}.\n"
        f"Links found: {link_lines}"
    )

    # 4. Each link references valid node IDs
    for link_line in link_lines:
        # Extract source (before -->)
        source_part = link_line.split("-->")[0].strip()
        assert source_part in node_ids, (
            f"Link source '{source_part}' not in node IDs: {node_ids}"
        )
        # Extract target (after --> or after |label|)
        after_arrow = link_line.split("-->")[1].strip()
        if "|" in after_arrow:
            # Format: |label| target_id
            target_part = after_arrow.split("|")[-1].strip()
        else:
            target_part = after_arrow.strip()
        assert target_part in node_ids, (
            f"Link target '{target_part}' not in node IDs: {node_ids}"
        )
