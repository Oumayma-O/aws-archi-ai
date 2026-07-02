# Feature: aws-architect-ai, Property 3: JSON extraction from wrapped text
"""
Property-based test: For any valid JSON object string embedded within arbitrary
non-JSON prefix and suffix text, the `extract_json` function SHALL extract a
string that, when parsed, produces the same object as parsing the original JSON
string directly.

**Validates: Requirements 3.1**
"""

import json

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from services.parser import extract_json


# Strategy: generate a valid JSON object as a dict, then serialize it
json_object_strategy = st.dictionaries(
    keys=st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N", "Pd"),
            min_codepoint=32,
            max_codepoint=126,
        ),
        min_size=1,
        max_size=10,
    ),
    values=st.one_of(
        st.text(max_size=50),
        st.integers(min_value=-1000, max_value=1000),
        st.floats(allow_nan=False, allow_infinity=False),
        st.booleans(),
        st.none(),
        st.lists(st.integers(min_value=-100, max_value=100), max_size=5),
    ),
    min_size=1,
    max_size=5,
)

# Strategy: prefix/suffix text that does NOT contain '{' to avoid confusing the parser
non_brace_text = st.text(
    alphabet=st.characters(
        blacklist_characters="{",
        min_codepoint=32,
        max_codepoint=126,
    ),
    min_size=0,
    max_size=100,
)


@given(
    obj=json_object_strategy,
    prefix=non_brace_text,
    suffix=non_brace_text,
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_json_extraction_from_wrapped_text(
    obj: dict, prefix: str, suffix: str
) -> None:
    """
    Property 3: JSON extraction from wrapped text.

    For any valid JSON object string embedded within arbitrary non-JSON prefix
    and suffix text (that doesn't contain '{'), the extract_json function SHALL
    extract a string that, when parsed, produces the same object as parsing the
    original JSON string directly.

    **Validates: Requirements 3.1**
    """
    json_str = json.dumps(obj)
    wrapped = prefix + json_str + suffix

    extracted = extract_json(wrapped)
    parsed_extracted = json.loads(extracted)
    parsed_original = json.loads(json_str)

    assert parsed_extracted == parsed_original, (
        f"Extracted JSON does not match original.\n"
        f"Original: {parsed_original!r}\n"
        f"Extracted: {parsed_extracted!r}\n"
        f"Wrapped input: {wrapped!r}"
    )
