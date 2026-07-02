"""Unit tests for the Generator page validation logic.

Tests the input validation independently since the page module
executes Streamlit code at import time.
"""

import pytest

from utils.validation import validate_input


def _validate_description(description: str) -> str | None:
    """Mirror the validation logic from the Generator page.

    This replicates the _validate_description function from
    pages/1_Generator.py for testability without importing
    the Streamlit page module.
    """
    if not validate_input(description):
        return "Please enter a system description. The input cannot be empty or whitespace-only."
    if len(description) > 5000:
        return f"Description exceeds maximum length of 5000 characters (current: {len(description)})."
    return None


class TestValidateDescription:
    """Tests for Generator page input validation."""

    def test_empty_string_rejected(self) -> None:
        """Empty string input should return an error message."""
        result = _validate_description("")
        assert result is not None
        assert "empty" in result.lower() or "required" in result.lower()

    def test_whitespace_only_rejected(self) -> None:
        """Whitespace-only input should return an error message."""
        result = _validate_description("   \t\n  ")
        assert result is not None
        assert "empty" in result.lower() or "required" in result.lower()

    def test_valid_input_accepted(self) -> None:
        """Non-empty, non-whitespace input within length limit should return None."""
        result = _validate_description("A web app with a database")
        assert result is None

    def test_exactly_5000_chars_accepted(self) -> None:
        """Input of exactly 5000 characters should be accepted."""
        result = _validate_description("a" * 5000)
        assert result is None

    def test_over_5000_chars_rejected(self) -> None:
        """Input exceeding 5000 characters should return an error message."""
        result = _validate_description("a" * 5001)
        assert result is not None
        assert "5000" in result

    def test_single_char_accepted(self) -> None:
        """A single non-whitespace character should be accepted."""
        result = _validate_description("x")
        assert result is None

    def test_newlines_only_rejected(self) -> None:
        """Input of only newline characters should be rejected."""
        result = _validate_description("\n\n\n")
        assert result is not None

    def test_mixed_content_with_whitespace_accepted(self) -> None:
        """Input with leading/trailing whitespace but valid content should pass."""
        result = _validate_description("  hello world  ")
        assert result is None
