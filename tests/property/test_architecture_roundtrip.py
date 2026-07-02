# Feature: aws-architect-ai, Property 4: Architecture model serialization round-trip
"""
Property-based test: For any valid ArchitectureModel instance, serializing it
to JSON via model_dump_json() and then parsing the resulting JSON back into an
ArchitectureModel via model_validate_json() SHALL produce an object that is
field-by-field equal to the original.

**Validates: Requirements 3.5**
"""

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from models.architecture import (
    ArchitectureModel,
    DiagramConnection,
    DiagramData,
    DiagramNode,
    EstimatedCost,
    MonitoringConfig,
    NetworkingConfig,
    ScalingConfig,
    SecurityConfig,
    ServiceCost,
    ServiceDetail,
)


# --- Custom Hypothesis Strategies ---

# Strategy for non-empty text fields (titles, labels, etc.)
non_empty_text = st.text(min_size=1, max_size=50, alphabet=st.characters(
    whitelist_categories=("L", "N", "P", "Z"),
    blacklist_characters="\x00",
))

# Strategy for identifier-like strings (node IDs)
identifier_text = st.text(
    min_size=1, max_size=20,
    alphabet=st.characters(whitelist_categories=("L", "N"), blacklist_characters="\x00"),
)

# Strategy for optional text (can be None)
optional_text = st.one_of(st.none(), non_empty_text)


@st.composite
def diagram_node_strategy(draw):
    """Generate a valid DiagramNode."""
    return DiagramNode(
        id=draw(identifier_text),
        label=draw(non_empty_text),
        aws_service=draw(non_empty_text),
    )


@st.composite
def diagram_connection_strategy(draw, node_ids):
    """Generate a valid DiagramConnection referencing given node IDs."""
    source_id = draw(st.sampled_from(node_ids))
    target_id = draw(st.sampled_from(node_ids))
    label = draw(optional_text)
    return DiagramConnection(source_id=source_id, target_id=target_id, label=label)


@st.composite
def service_detail_strategy(draw):
    """Generate a valid ServiceDetail."""
    return ServiceDetail(
        name=draw(non_empty_text),
        role=draw(non_empty_text),
    )


@st.composite
def service_cost_strategy(draw):
    """Generate a valid ServiceCost."""
    return ServiceCost(
        service=draw(non_empty_text),
        monthly_cost=draw(non_empty_text),
    )


@st.composite
def estimated_cost_strategy(draw):
    """Generate a valid EstimatedCost."""
    breakdown = draw(st.lists(service_cost_strategy(), min_size=0, max_size=5))
    return EstimatedCost(
        total_monthly=draw(non_empty_text),
        breakdown=breakdown,
    )


@st.composite
def security_config_strategy(draw):
    """Generate a valid SecurityConfig."""
    str_list = st.lists(non_empty_text, min_size=0, max_size=3)
    return SecurityConfig(
        iam_policies=draw(str_list),
        encryption=draw(str_list),
        cloudtrail=draw(str_list),
        waf_rules=draw(str_list),
        recommendations=draw(str_list),
    )


@st.composite
def networking_config_strategy(draw):
    """Generate a valid NetworkingConfig."""
    str_list = st.lists(non_empty_text, min_size=0, max_size=3)
    return NetworkingConfig(
        vpc=draw(non_empty_text),
        subnets=draw(str_list),
        security_groups=draw(str_list),
        load_balancers=draw(str_list),
    )


@st.composite
def scaling_config_strategy(draw):
    """Generate a valid ScalingConfig."""
    return ScalingConfig(
        strategy=draw(non_empty_text),
        policies=draw(st.lists(non_empty_text, min_size=0, max_size=3)),
    )


@st.composite
def monitoring_config_strategy(draw):
    """Generate a valid MonitoringConfig."""
    str_list = st.lists(non_empty_text, min_size=0, max_size=3)
    return MonitoringConfig(
        cloudwatch_metrics=draw(str_list),
        alarms=draw(str_list),
        dashboards=draw(str_list),
    )


@st.composite
def diagram_data_strategy(draw):
    """Generate a valid DiagramData with consistent node references."""
    nodes = draw(st.lists(diagram_node_strategy(), min_size=0, max_size=5))
    if nodes:
        node_ids = [n.id for n in nodes]
        connections = draw(
            st.lists(diagram_connection_strategy(node_ids), min_size=0, max_size=5)
        )
    else:
        connections = []
    return DiagramData(nodes=nodes, connections=connections)


@st.composite
def architecture_model_strategy(draw):
    """Generate a valid ArchitectureModel instance."""
    return ArchitectureModel(
        title=draw(non_empty_text),
        summary=draw(non_empty_text),
        architecture_description=draw(non_empty_text),
        aws_services=draw(st.lists(service_detail_strategy(), min_size=1, max_size=5)),
        networking=draw(networking_config_strategy()),
        security=draw(security_config_strategy()),
        scaling=draw(scaling_config_strategy()),
        monitoring=draw(monitoring_config_strategy()),
        estimated_cost=draw(estimated_cost_strategy()),
        diagram=draw(diagram_data_strategy()),
        recommendations=draw(st.lists(non_empty_text, min_size=0, max_size=5)),
    )


@given(model=architecture_model_strategy())
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_architecture_model_serialization_roundtrip(model: ArchitectureModel):
    """
    Property 4: Architecture model serialization round-trip.

    For any valid ArchitectureModel instance, serializing to JSON and parsing
    back SHALL produce an object field-by-field equal to the original.

    **Validates: Requirements 3.5**
    """
    # Serialize to JSON
    json_str = model.model_dump_json()

    # Parse back from JSON
    restored = ArchitectureModel.model_validate_json(json_str)

    # Assert field-by-field equality
    assert restored == model
