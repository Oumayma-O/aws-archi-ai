# Feature: aws-architect-ai, Property 1: Whitespace-only input is always rejected
"""
Property-based test: For any string composed entirely of whitespace characters
(spaces, tabs, newlines, carriage returns, or any combination thereof), the input
validation function SHALL reject it and return a validation error, leaving
application state unchanged.

**Validates: Requirements 1.3**
"""

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from utils.validation import validate_input


# Strategy that generates strings composed entirely of whitespace characters
# including spaces, tabs, newlines, carriage returns, and Unicode whitespace
WHITESPACE_CHARS = " \t\n\r\x0b\x0c"
whitespace_only_strategy = st.text(
    alphabet=WHITESPACE_CHARS,
    min_size=1,
)


@given(whitespace_input=whitespace_only_strategy)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_whitespace_only_input_is_rejected(whitespace_input: str) -> None:
    """
    Property 1: Whitespace-only input is always rejected.

    For any string composed entirely of whitespace characters (spaces, tabs,
    newlines, carriage returns, or any combination thereof), the input validation
    function SHALL reject it and return False.

    **Validates: Requirements 1.3**
    """
    result = validate_input(whitespace_input)
    assert result is False, (
        f"Expected whitespace-only input to be rejected (False), "
        f"but got {result!r} for input: {whitespace_input!r}"
    )


@given(whitespace_input=st.text(alphabet=WHITESPACE_CHARS, min_size=0))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_empty_and_whitespace_input_is_rejected(whitespace_input: str) -> None:
    """
    Supplementary property: Empty strings are also rejected.

    For any string that is empty or composed entirely of whitespace characters,
    validate_input SHALL return False.

    **Validates: Requirements 1.3**
    """
    result = validate_input(whitespace_input)
    assert result is False, (
        f"Expected empty/whitespace-only input to be rejected (False), "
        f"but got {result!r} for input: {whitespace_input!r}"
    )
