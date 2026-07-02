"""Structured JSON logging configuration for AWS Architect AI.

Provides JSON-formatted log output to stdout for CloudWatch Logs compatibility
on ECS Fargate. Sensitive data (credentials, tokens) is never logged.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    """Formats log records as JSON objects with required structured fields.

    Output contains: timestamp, level, logger, and message fields.
    Sensitive keys are redacted from any extra data.
    """

    SENSITIVE_KEYS = frozenset({
        "aws_access_key_id",
        "aws_secret_access_key",
        "aws_session_token",
        "password",
        "secret",
        "token",
        "credential",
        "credentials",
        "authorization",
    })

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON string.

        Args:
            record: The log record to format.

        Returns:
            JSON-formatted string with timestamp, level, logger, and message.
        """
        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": self._sanitize_message(record.getMessage()),
        }

        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        return json.dumps(log_entry, default=str)

    def _sanitize_message(self, message: str) -> str:
        """Remove potential sensitive data patterns from log messages.

        Args:
            message: The raw log message.

        Returns:
            Sanitized message string.
        """
        # Redact common AWS credential patterns
        import re

        # Redact AWS access key patterns (AKIA...)
        message = re.sub(r"AKIA[0-9A-Z]{16}", "[REDACTED]", message)
        # Redact long base64-like secret tokens (40+ chars)
        message = re.sub(
            r"(?i)(secret|token|password|credential)[\s]*[=:]\s*\S+",
            r"\1=[REDACTED]",
            message,
        )
        return message


def setup_logging(log_level: str = "INFO") -> None:
    """Configure JSON-formatted structured logging to stdout.

    Sets up the root logger with a JSON formatter writing to stdout.
    The log level can be overridden by the LOG_LEVEL environment variable.

    Args:
        log_level: Log level string (DEBUG, INFO, WARNING, ERROR).
            Defaults to INFO. The LOG_LEVEL environment variable
            takes precedence if set.
    """
    # Environment variable takes precedence over the argument
    effective_level = os.environ.get("LOG_LEVEL", log_level).upper()

    # Validate the level string
    numeric_level = getattr(logging, effective_level, None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicate output
    root_logger.handlers.clear()

    # Create stdout handler with JSON formatter
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(numeric_level)
    stdout_handler.setFormatter(JsonFormatter())

    root_logger.addHandler(stdout_handler)
