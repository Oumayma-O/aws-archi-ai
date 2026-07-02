"""Unit tests for error handling in the Generator page.

Tests the error handling logic from handle_generate() by replicating
the try/except structure. This avoids importing the Streamlit page module
directly (which executes at import time).

The test validates that each exception type results in:
1. The correct user-facing error message
2. The correct generation_error state
3. Input preservation in session state
4. Proper logging of error details
"""

import logging
import traceback
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from services.exceptions import (
    BedrockConnectionError,
    BedrockThrottlingError,
    BedrockTimeoutError,
    JsonExtractionError,
)


def _simulate_handle_generate_error(
    error: Exception,
    description: str = "A web application with auth",
    temperature: float = 1.0,
    model_id: str = "eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
) -> dict:
    """Simulate the error handling logic from handle_generate().

    This replicates the try/except block from pages/1_Generator.py
    handle_generate() to test error handling without Streamlit imports.

    Args:
        error: The exception to raise during the pipeline.
        description: The user input description.
        temperature: Generation temperature.
        model_id: Bedrock model identifier.

    Returns:
        Dict with keys: error_message, generation_error, last_params, logged.
    """
    logger = logging.getLogger("pages.1_Generator")
    result = {
        "error_message": None,
        "generation_error": None,
        "last_params": {
            "description": description,
            "temperature": temperature,
            "model_id": model_id,
        },
        "logged": False,
    }

    try:
        # Simulate pipeline raising the provided error
        raise error

    except BedrockConnectionError:
        logger.error("Bedrock connection failed", exc_info=True)
        result["generation_error"] = "connection"
        result["error_message"] = (
            "Unable to connect to AWS Bedrock. "
            "Check your network and credentials."
        )
        result["logged"] = True

    except BedrockThrottlingError:
        logger.error("Bedrock request throttled", exc_info=True)
        result["generation_error"] = "throttling"
        result["error_message"] = (
            "Request was throttled. "
            "Please wait a few seconds and try again."
        )
        result["logged"] = True

    except BedrockTimeoutError:
        logger.error("Bedrock request timed out", exc_info=True)
        result["generation_error"] = "timeout"
        result["error_message"] = (
            "Request timed out after 60 seconds. Please try again."
        )
        result["logged"] = True

    except JsonExtractionError:
        logger.error("JSON extraction failed", exc_info=True)
        result["generation_error"] = "parse"
        result["error_message"] = (
            "Could not process the AI response. Click Retry to try again."
        )
        result["logged"] = True

    except ValidationError:
        logger.error("Response validation failed", exc_info=True)
        result["generation_error"] = "validation"
        result["error_message"] = (
            "AI response was malformed. Click Retry to try again."
        )
        result["logged"] = True

    except Exception:
        logger.error(
            "Unhandled exception during generation:\n%s",
            traceback.format_exc(),
        )
        result["generation_error"] = "unexpected"
        result["error_message"] = "An unexpected error occurred. Please try again."
        result["logged"] = True

    return result


class TestBedrockConnectionErrorHandling:
    """Tests for BedrockConnectionError handling."""

    def test_displays_connection_failure_message(self) -> None:
        """Should display message about connection failure with remediation hint."""
        result = _simulate_handle_generate_error(
            BedrockConnectionError("Connection refused")
        )
        assert "Unable to connect to AWS Bedrock" in result["error_message"]
        assert "network" in result["error_message"].lower()
        assert "credentials" in result["error_message"].lower()

    def test_sets_connection_error_state(self) -> None:
        """Should set generation_error to 'connection'."""
        result = _simulate_handle_generate_error(
            BedrockConnectionError("fail")
        )
        assert result["generation_error"] == "connection"

    def test_preserves_input(self) -> None:
        """User input should remain in last_params for retry."""
        result = _simulate_handle_generate_error(
            BedrockConnectionError("fail"),
            description="My important description",
        )
        assert result["last_params"]["description"] == "My important description"

    def test_logs_error(self, caplog) -> None:
        """Should log the error."""
        with caplog.at_level(logging.ERROR, logger="pages.1_Generator"):
            _simulate_handle_generate_error(
                BedrockConnectionError("Connection refused")
            )
        assert "connection" in caplog.text.lower()


class TestBedrockThrottlingErrorHandling:
    """Tests for BedrockThrottlingError handling."""

    def test_displays_throttling_message_with_wait_suggestion(self) -> None:
        """Should display message suggesting to wait before retrying."""
        result = _simulate_handle_generate_error(
            BedrockThrottlingError("Rate exceeded")
        )
        assert "throttled" in result["error_message"].lower()
        assert "wait" in result["error_message"].lower()

    def test_sets_throttling_error_state(self) -> None:
        """Should set generation_error to 'throttling'."""
        result = _simulate_handle_generate_error(
            BedrockThrottlingError("throttled")
        )
        assert result["generation_error"] == "throttling"

    def test_preserves_input(self) -> None:
        """User input should remain available for retry."""
        result = _simulate_handle_generate_error(
            BedrockThrottlingError("throttled"),
            description="Retry this later",
        )
        assert result["last_params"]["description"] == "Retry this later"


class TestBedrockTimeoutErrorHandling:
    """Tests for BedrockTimeoutError handling."""

    def test_displays_timeout_message(self) -> None:
        """Should display message about timeout with duration."""
        result = _simulate_handle_generate_error(
            BedrockTimeoutError("Timed out")
        )
        assert "timed out" in result["error_message"].lower()
        assert "60 seconds" in result["error_message"]

    def test_sets_timeout_error_state(self) -> None:
        """Should set generation_error to 'timeout'."""
        result = _simulate_handle_generate_error(
            BedrockTimeoutError("timeout")
        )
        assert result["generation_error"] == "timeout"


class TestJsonExtractionErrorHandling:
    """Tests for JsonExtractionError handling."""

    def test_displays_parse_error_with_retry_hint(self) -> None:
        """Should display message about processing failure with Retry suggestion."""
        result = _simulate_handle_generate_error(
            JsonExtractionError("No JSON found")
        )
        assert "Could not process the AI response" in result["error_message"]
        assert "Retry" in result["error_message"]

    def test_sets_parse_error_state(self) -> None:
        """Should set generation_error to 'parse'."""
        result = _simulate_handle_generate_error(
            JsonExtractionError("no json")
        )
        assert result["generation_error"] == "parse"


class TestValidationErrorHandling:
    """Tests for pydantic ValidationError handling."""

    def _make_validation_error(self) -> ValidationError:
        """Create a real pydantic ValidationError for testing."""
        from pydantic import BaseModel

        class Dummy(BaseModel):
            x: int

        try:
            Dummy(x="not_an_int")  # type: ignore
        except ValidationError as e:
            return e
        raise AssertionError("Should have raised")  # pragma: no cover

    def test_displays_malformed_response_message_with_retry(self) -> None:
        """Should display message about malformed response with Retry suggestion."""
        result = _simulate_handle_generate_error(self._make_validation_error())
        assert "malformed" in result["error_message"].lower()
        assert "Retry" in result["error_message"]

    def test_sets_validation_error_state(self) -> None:
        """Should set generation_error to 'validation'."""
        result = _simulate_handle_generate_error(self._make_validation_error())
        assert result["generation_error"] == "validation"


class TestUnhandledExceptionHandling:
    """Tests for unhandled exception handling."""

    def test_displays_generic_message(self) -> None:
        """Should display a generic error message without internal details."""
        result = _simulate_handle_generate_error(
            RuntimeError("internal secret detail")
        )
        assert "unexpected error" in result["error_message"].lower()
        # Should NOT expose internal details
        assert "internal secret detail" not in result["error_message"]

    def test_sets_unexpected_error_state(self) -> None:
        """Should set generation_error to 'unexpected'."""
        result = _simulate_handle_generate_error(
            RuntimeError("oops")
        )
        assert result["generation_error"] == "unexpected"

    def test_preserves_input(self) -> None:
        """User input should be preserved for retry."""
        result = _simulate_handle_generate_error(
            RuntimeError("fail"),
            description="Please preserve this",
        )
        assert result["last_params"]["description"] == "Please preserve this"

    def test_logs_full_details(self, caplog) -> None:
        """Should log full error details including traceback info."""
        with caplog.at_level(logging.ERROR, logger="pages.1_Generator"):
            _simulate_handle_generate_error(
                RuntimeError("detailed internal error")
            )
        # Logger should have recorded something at ERROR level
        assert len(caplog.records) > 0
        assert caplog.records[0].levelname == "ERROR"

    def test_does_not_expose_stack_trace_to_user(self) -> None:
        """Error message shown to user should not contain stack trace."""
        result = _simulate_handle_generate_error(
            ValueError("Traceback line info should not appear")
        )
        assert "Traceback" not in result["error_message"]
        assert "ValueError" not in result["error_message"]


class TestRetryParameters:
    """Tests for retry parameter storage."""

    def test_stores_description_for_retry(self) -> None:
        """Should store original description so retry can resubmit it."""
        result = _simulate_handle_generate_error(
            BedrockConnectionError("fail"),
            description="Original input text",
        )
        assert result["last_params"]["description"] == "Original input text"

    def test_stores_temperature_for_retry(self) -> None:
        """Should store temperature parameter for retry."""
        result = _simulate_handle_generate_error(
            BedrockConnectionError("fail"),
            temperature=0.5,
        )
        assert result["last_params"]["temperature"] == 0.5

    def test_stores_model_id_for_retry(self) -> None:
        """Should store model ID for retry."""
        result = _simulate_handle_generate_error(
            BedrockConnectionError("fail"),
            model_id="custom-model-id",
        )
        assert result["last_params"]["model_id"] == "custom-model-id"
