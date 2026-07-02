# Feature: aws-architect-ai, Property 2: Prompt builder includes all required elements
"""
Property-based test: For any non-empty system description string, the prompt
produced by `build_prompt` SHALL contain the original description text verbatim
AND contain all required response field names (title, summary,
architecture_description, aws_services, networking, security, scaling,
monitoring, estimated_cost, diagram, recommendations).

**Validates: Requirements 2.1**
"""

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from services.prompt_builder import build_prompt


# All required field names that must appear in the generated prompt
REQUIRED_FIELDS = [
    "title",
    "summary",
    "architecture_description",
    "aws_services",
    "networking",
    "security",
    "scaling",
    "monitoring",
    "estimated_cost",
    "diagram",
    "recommendations",
]


@given(description=st.text(min_size=1, max_size=5000))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_prompt_contains_description_and_required_fields(description: str):
    """
    Property 2: Prompt builder includes all required elements.

    For any non-empty system description string, the prompt produced by
    build_prompt SHALL contain the original description text verbatim AND
    contain all required response field names.

    **Validates: Requirements 2.1**
    """
    prompt = build_prompt(description)

    # The prompt must contain the original description verbatim
    assert description in prompt, (
        f"Prompt does not contain the original description verbatim. "
        f"Description: {description!r}"
    )

    # The prompt must contain all required field names
    for field in REQUIRED_FIELDS:
        assert field in prompt, (
            f"Prompt is missing required field name: '{field}'"
        )
