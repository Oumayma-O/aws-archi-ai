"""Unit tests for utils/logging.py structured JSON logging."""

import json
import logging
import os
from unittest.mock import patch

import pytest

from utils.logging import JsonFormatter, setup_logging


class TestJsonFormatter:
    """Tests for the JsonFormatter class."""

    def setup_method(self) -> None:
        """Set up a fresh formatter for each test."""
        self.formatter = JsonFormatter()

    def test_format_produces_valid_json(self) -> None:
        """Log output must be valid JSON."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Hello world",
            args=None,
            exc_info=None,
        )
        output = self.formatter.format(record)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_format_contains_required_fields(self) -> None:
        """Output JSON must contain timestamp, level, logger, message."""
        record = logging.LogRecord(
            name="myapp.services",
            level=logging.WARNING,
            pathname="test.py",
            lineno=10,
            msg="Something happened",
            args=None,
            exc_info=None,
        )
        output = self.formatter.format(record)
        parsed = json.loads(output)

        assert "timestamp" in parsed
        assert "level" in parsed
        assert "logger" in parsed
        assert "message" in parsed

    def test_level_field_matches_record(self) -> None:
        """Level field should match the log level name."""
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="An error",
            args=None,
            exc_info=None,
        )
        output = self.formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "ERROR"

    def test_logger_field_matches_record_name(self) -> None:
        """Logger field should match the logger name."""
        record = logging.LogRecord(
            name="services.bedrock",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="request sent",
            args=None,
            exc_info=None,
        )
        output = self.formatter.format(record)
        parsed = json.loads(output)
        assert parsed["logger"] == "services.bedrock"

    def test_message_field_contains_log_message(self) -> None:
        """Message field should contain the original log message."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Model invoked successfully",
            args=None,
            exc_info=None,
        )
        output = self.formatter.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "Model invoked successfully"

    def test_timestamp_is_iso_format(self) -> None:
        """Timestamp should be in ISO 8601 format."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test",
            args=None,
            exc_info=None,
        )
        output = self.formatter.format(record)
        parsed = json.loads(output)
        # ISO format should contain T separator and timezone info
        assert "T" in parsed["timestamp"]

    def test_exception_info_included(self) -> None:
        """Exception info should be included when present."""
        try:
            raise ValueError("test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="An error occurred",
            args=None,
            exc_info=exc_info,
        )
        output = self.formatter.format(record)
        parsed = json.loads(output)
        assert "exception" in parsed
        assert parsed["exception"]["type"] == "ValueError"
        assert "test error" in parsed["exception"]["message"]

    def test_sanitize_aws_access_key(self) -> None:
        """AWS access key patterns should be redacted."""
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="Key found: AKIAIOSFODNN7EXAMPLE",
            args=None,
            exc_info=None,
        )
        output = self.formatter.format(record)
        parsed = json.loads(output)
        assert "AKIAIOSFODNN7EXAMPLE" not in parsed["message"]
        assert "[REDACTED]" in parsed["message"]

    def test_sanitize_secret_token_pattern(self) -> None:
        """Secret/token/password patterns should be redacted."""
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="secret=mysupersecretvalue123",
            args=None,
            exc_info=None,
        )
        output = self.formatter.format(record)
        parsed = json.loads(output)
        assert "mysupersecretvalue123" not in parsed["message"]
        assert "[REDACTED]" in parsed["message"]


class TestSetupLogging:
    """Tests for the setup_logging function."""

    def teardown_method(self) -> None:
        """Clean up root logger after each test."""
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(logging.WARNING)
        # Clear LOG_LEVEL env var if set
        os.environ.pop("LOG_LEVEL", None)

    def test_default_level_is_info(self) -> None:
        """Default log level should be INFO."""
        setup_logging()
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

    def test_custom_level_argument(self) -> None:
        """Custom log level argument should be respected."""
        setup_logging("DEBUG")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_env_variable_overrides_argument(self) -> None:
        """LOG_LEVEL env var should override the function argument."""
        os.environ["LOG_LEVEL"] = "ERROR"
        setup_logging("DEBUG")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.ERROR

    def test_invalid_level_defaults_to_info(self) -> None:
        """An invalid log level string should fallback to INFO."""
        setup_logging("INVALID_LEVEL")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

    def test_handler_writes_to_stdout(self) -> None:
        """Logger should write to stdout."""
        import sys

        setup_logging()
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) == 1
        handler = root_logger.handlers[0]
        assert isinstance(handler, logging.StreamHandler)
        assert handler.stream is sys.stdout

    def test_handler_uses_json_formatter(self) -> None:
        """Handler should use JsonFormatter."""
        setup_logging()
        root_logger = logging.getLogger()
        handler = root_logger.handlers[0]
        assert isinstance(handler.formatter, JsonFormatter)

    def test_no_duplicate_handlers_on_multiple_calls(self) -> None:
        """Calling setup_logging multiple times should not add duplicate handlers."""
        setup_logging()
        setup_logging()
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) == 1

    def test_case_insensitive_env_level(self) -> None:
        """LOG_LEVEL env var should be case insensitive."""
        os.environ["LOG_LEVEL"] = "warning"
        setup_logging()
        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING
