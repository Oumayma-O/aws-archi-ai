# Feature: aws-architect-ai, Property 8: Filename sanitization produces valid filenames
"""
Property-based test: For any architecture title string, format name, and extension,
the `generate_export_filename` function SHALL produce a string that:
(a) contains no characters other than alphanumeric, underscores, hyphens, and a
    single dot before the extension,
(b) ends with `_{format}.{extension}`, and
(c) is non-empty in the title portion (using a fallback for empty/whitespace-only titles).

**Validates: Requirements 6.5**
"""

import re

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from utils.export import generate_export_filename, sanitize_filename


# Strategy for format names: alphanumeric only for simplicity
format_name_strategy = st.from_regex(r"[a-zA-Z0-9]+", fullmatch=True).filter(
    lambda s: len(s) >= 1 and len(s) <= 20
)

# Strategy for extensions: alphanumeric only
extension_strategy = st.from_regex(r"[a-zA-Z0-9]+", fullmatch=True).filter(
    lambda s: len(s) >= 1 and len(s) <= 10
)

# Strategy for titles: any text including edge cases
title_strategy = st.text(min_size=0, max_size=200)


@given(
    title=title_strategy,
    format_name=format_name_strategy,
    extension=extension_strategy,
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_filename_sanitization_produces_valid_filenames(
    title: str, format_name: str, extension: str
):
    """
    Property 8: Filename sanitization produces valid filenames.

    For any architecture title string, format name, and extension, the
    generate_export_filename function SHALL produce a string that:
    (a) contains no characters other than alphanumeric, underscores, hyphens,
        and a single dot before the extension,
    (b) ends with _{format}.{extension}, and
    (c) is non-empty in the title portion (using a fallback for
        empty/whitespace-only titles).

    **Validates: Requirements 6.5**
    """
    result = generate_export_filename(title, format_name, extension)

    # (c) The result must be non-empty
    assert len(result) > 0, "Generated filename must not be empty"

    # (b) The filename must end with _{format_name}.{extension}
    expected_suffix = f"_{format_name}.{extension}"
    assert result.endswith(expected_suffix), (
        f"Filename must end with '{expected_suffix}', got: '{result}'"
    )

    # Extract the title portion (everything before the suffix)
    title_portion = result[: -len(expected_suffix)]

    # (c) The title portion must be non-empty (fallback used for empty/whitespace titles)
    assert len(title_portion) > 0, (
        f"Title portion of filename must not be empty, got: '{result}'"
    )

    # (a) The title portion must contain only alphanumeric, underscores, and hyphens
    assert re.fullmatch(r"[a-zA-Z0-9_\-]+", title_portion), (
        f"Title portion contains invalid characters: '{title_portion}'"
    )

    # (a) The full filename must contain only one dot (before the extension)
    # Split on the last dot to verify structure
    dot_count = result.count(".")
    assert dot_count == 1, (
        f"Filename must contain exactly one dot (before extension), "
        f"got {dot_count} dots in: '{result}'"
    )


@given(title=st.text(min_size=0, max_size=200))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_sanitize_filename_produces_safe_output(title: str):
    """
    Supplementary property: sanitize_filename always returns a non-empty string
    containing only alphanumeric characters, underscores, and hyphens.

    **Validates: Requirements 6.5**
    """
    result = sanitize_filename(title)

    # Result must never be empty
    assert len(result) > 0, "sanitize_filename must never return an empty string"

    # Result must contain only safe characters
    assert re.fullmatch(r"[a-zA-Z0-9_\-]+", result), (
        f"sanitize_filename produced invalid characters: '{result}'"
    )
