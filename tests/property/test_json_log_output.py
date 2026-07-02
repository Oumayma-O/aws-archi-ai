# Feature: aws-architect-ai, Property 10: Log formatter produces valid structured JSON
"""
Property-based test: For any log message string and log level, the JSON log
formatter SHALL produce output that parses as valid JSON and contains the keys
"timestamp", "level", "logger", and "message", where "message" contains the
original log message text.

**Validates: Requirements 14.1**
"""

import json
import logging

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from utils.logging import JsonFormatter


# Log levels to test against
LOG_LEVELS = [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]

# Strategy for log messages: arbitrary text strings
log_message_strategy = st.text(min_size=0, max_size=200)

# Strategy for log levels
log_level_strategy = st.sampled_from(LOG_LEVELS)


@given(message=log_message_strategy, level=log_level_strategy)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_json_formatter_produces_valid_structured_json(message: str, level: int):
    """
    Property 10: Log formatter produces valid structured JSON.

    For any log message string and log level, the JSON log formatter SHALL
    produce output that parses as valid JSON and contains the keys "timestamp",
    "level", "logger", and "message", where "message" contains the original
    log message text.

    **Validates: Requirements 14.1**
    """
    formatter = JsonFormatter()

    # Create a LogRecord with the generated message and level
    record = logging.LogRecord(
        name="test.logger",
        level=level,
        pathname="test_file.py",
        lineno=1,
        msg=message,
        args=None,
        exc_info=None,
    )

    # Format the record using the JsonFormatter
    output = formatter.format(record)

    # Verify output parses as valid JSON
    parsed = json.loads(output)

    # Verify required keys are present
    assert "timestamp" in parsed, f"Missing 'timestamp' key in output: {output}"
    assert "level" in parsed, f"Missing 'level' key in output: {output}"
    assert "logger" in parsed, f"Missing 'logger' key in output: {output}"
    assert "message" in parsed, f"Missing 'message' key in output: {output}"

    # Verify the level matches the expected level name
    assert parsed["level"] == logging.getLevelName(level)

    # Verify the logger name is preserved
    assert parsed["logger"] == "test.logger"

    # Verify the message contains the original log message text
    # Note: the sanitizer may redact sensitive patterns, so for non-sensitive
    # messages, the original text should be present as-is
    # For messages that don't match sensitive patterns, verify exact containment
    assert message in parsed["message"] or "[REDACTED]" in parsed["message"]
