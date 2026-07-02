# Feature: aws-architect-ai, Property 7: Mermaid conversion round-trip preserves structure
"""
Property-based test: For any list of DiagramNode objects and list of
DiagramConnection objects (where all connections reference valid node ids),
converting to Mermaid code via to_mermaid and then parsing back via
parse_mermaid SHALL preserve all node ids, all node labels, and all
connections (source_id, target_id pairs).

**Validates: Requirements 13.5**
"""

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from models.architecture import DiagramConnection, DiagramNode
from services.diagram import parse_mermaid, to_mermaid


# --- Custom Hypothesis Strategies ---

# Node IDs must be valid Mermaid identifiers: start with a letter, then
# alphanumeric/underscore characters (matching regex \w+).
mermaid_node_id = st.from_regex(r"[a-zA-Z][a-zA-Z0-9_]{0,14}", fullmatch=True)

# Labels must be simple alphanumeric text without parentheses, quotes, or
# special Mermaid characters. This avoids breaking the "Label (aws_service)"
# parsing format.
simple_label = st.text(
    min_size=1,
    max_size=30,
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        blacklist_characters='()[]"#|{}\n\r',
    ),
)

# AWS service names follow the same constraints as labels
aws_service_name = st.text(
    min_size=1,
    max_size=15,
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        blacklist_characters='()[]"#|{}\n\r',
    ),
)

# Optional connection labels — same constraints as node labels
optional_conn_label = st.one_of(
    st.none(),
    st.text(
        min_size=1,
        max_size=20,
        alphabet=st.characters(
            whitelist_categories=("L", "N"),
            blacklist_characters='()[]"#|{}\n\r',
        ),
    ),
)


@st.composite
def unique_diagram_nodes(draw, min_size=1, max_size=8):
    """Generate a list of DiagramNodes with unique IDs."""
    # Generate unique IDs first
    num_nodes = draw(st.integers(min_value=min_size, max_value=max_size))
    ids = draw(
        st.lists(
            mermaid_node_id,
            min_size=num_nodes,
            max_size=num_nodes,
            unique=True,
        )
    )
    nodes = []
    for node_id in ids:
        label = draw(simple_label)
        service = draw(aws_service_name)
        nodes.append(DiagramNode(id=node_id, label=label, aws_service=service))
    return nodes


@st.composite
def valid_connections(draw, node_ids):
    """Generate connections that only reference existing node IDs."""
    if len(node_ids) < 2:
        return []
    num_connections = draw(st.integers(min_value=0, max_value=min(len(node_ids) * 2, 10)))
    connections = []
    for _ in range(num_connections):
        source = draw(st.sampled_from(node_ids))
        target = draw(st.sampled_from(node_ids))
        label = draw(optional_conn_label)
        connections.append(
            DiagramConnection(source_id=source, target_id=target, label=label)
        )
    return connections


@st.composite
def diagram_with_connections(draw):
    """Generate a valid set of nodes and connections for Mermaid rendering."""
    nodes = draw(unique_diagram_nodes(min_size=1, max_size=8))
    node_ids = [n.id for n in nodes]
    connections = draw(valid_connections(node_ids))
    return nodes, connections


@given(data=diagram_with_connections())
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_mermaid_roundtrip_preserves_structure(data):
    """
    Property 7: Mermaid conversion round-trip preserves structure.

    For any list of DiagramNode objects and DiagramConnection objects (where
    all connections reference valid node IDs), converting to Mermaid via
    to_mermaid and parsing back via parse_mermaid SHALL preserve all node IDs,
    all node labels, all node aws_service values, and all connections
    (source_id, target_id pairs).

    **Validates: Requirements 13.5**
    """
    nodes, connections = data

    # Convert to Mermaid
    mermaid_code = to_mermaid(nodes, connections)

    # Parse back
    parsed_nodes, parsed_connections = parse_mermaid(mermaid_code)

    # Verify all node IDs are preserved
    original_ids = {n.id for n in nodes}
    parsed_ids = {n.id for n in parsed_nodes}
    assert original_ids == parsed_ids, (
        f"Node IDs mismatch. Original: {original_ids}, Parsed: {parsed_ids}"
    )

    # Verify all node labels are preserved
    original_labels = {n.id: n.label for n in nodes}
    parsed_labels = {n.id: n.label for n in parsed_nodes}
    assert original_labels == parsed_labels, (
        f"Node labels mismatch. Original: {original_labels}, Parsed: {parsed_labels}"
    )

    # Verify all node aws_service values are preserved
    original_services = {n.id: n.aws_service for n in nodes}
    parsed_services = {n.id: n.aws_service for n in parsed_nodes}
    assert original_services == parsed_services, (
        f"AWS services mismatch. Original: {original_services}, Parsed: {parsed_services}"
    )

    # Verify all connections are preserved (source_id, target_id, label tuples)
    # We check the full connection data including labels in the next assertion,
    # so here we just verify count matches as a precondition.
    assert len(connections) == len(parsed_connections), (
        f"Connection count mismatch. Original: {len(connections)}, "
        f"Parsed: {len(parsed_connections)}"
    )

    # Verify connection labels are preserved
    def conn_sort_key(c):
        return (c[0], c[1], c[2] or "")

    original_conn_labels = sorted(
        [(c.source_id, c.target_id, c.label) for c in connections],
        key=conn_sort_key,
    )
    parsed_conn_labels = sorted(
        [(c.source_id, c.target_id, c.label) for c in parsed_connections],
        key=conn_sort_key,
    )
    assert original_conn_labels == parsed_conn_labels, (
        f"Connection labels mismatch. Original: {original_conn_labels}, "
        f"Parsed: {parsed_conn_labels}"
    )
