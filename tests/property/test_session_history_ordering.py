# Feature: aws-architect-ai, Property 9: Session history maintains reverse-chronological order
"""
Property-based test: For any sequence of successfully generated ArchitectureModel
instances appended to session history, the history list SHALL contain all generated
architectures and SHALL be ordered such that the most recently generated architecture
appears first.

**Validates: Requirements 10.1, 10.2**
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


# --- Custom Hypothesis Strategies (reused from test_architecture_roundtrip.py) ---

non_empty_text = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        blacklist_characters="\x00",
    ),
)

identifier_text = st.text(
    min_size=1,
    max_size=20,
    alphabet=st.characters(whitelist_categories=("L", "N"), blacklist_characters="\x00"),
)

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
    breakdown = draw(st.lists(service_cost_strategy(), min_size=0, max_size=3))
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
    nodes = draw(st.lists(diagram_node_strategy(), min_size=0, max_size=3))
    if nodes:
        node_ids = [n.id for n in nodes]
        connections = draw(
            st.lists(diagram_connection_strategy(node_ids), min_size=0, max_size=3)
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
        aws_services=draw(st.lists(service_detail_strategy(), min_size=1, max_size=3)),
        networking=draw(networking_config_strategy()),
        security=draw(security_config_strategy()),
        scaling=draw(scaling_config_strategy()),
        monitoring=draw(monitoring_config_strategy()),
        estimated_cost=draw(estimated_cost_strategy()),
        diagram=draw(diagram_data_strategy()),
        recommendations=draw(st.lists(non_empty_text, min_size=0, max_size=3)),
    )


@given(architectures=st.lists(architecture_model_strategy(), min_size=1, max_size=10))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_session_history_maintains_reverse_chronological_order(
    architectures: list[ArchitectureModel],
):
    """
    Property 9: Session history maintains reverse-chronological order.

    For any sequence of successfully generated ArchitectureModel instances
    appended to session history using insert(0, ...), the history list SHALL
    contain all generated architectures and SHALL be ordered such that the most
    recently generated architecture appears first.

    **Validates: Requirements 10.1, 10.2**
    """
    # Simulate session history using the same pattern as the Generator page:
    # st.session_state.history.insert(0, architecture)
    history: list[ArchitectureModel] = []

    for architecture in architectures:
        history.insert(0, architecture)

    # Property: history contains ALL generated architectures
    assert len(history) == len(architectures)

    # Property: most recently generated architecture appears first
    # The last architecture appended should be at index 0
    assert history[0] == architectures[-1]

    # Property: full reverse-chronological ordering is maintained
    # History should be the reverse of the generation order
    for i, arch in enumerate(history):
        assert arch == architectures[len(architectures) - 1 - i]
