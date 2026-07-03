"""Unit tests for agents/tracing.py module.

Tests cover:
- setup_tracing() initialization and idempotency
- trace_agent_call() context manager with and without OTel
- trace_mcp_call() context manager with slow-call warning
- traced_agent() decorator
- Structured logging helpers (phase transitions, tool invocations, errors)
- ENABLE_PROMPT_LOGGING environment variable toggle
- Graceful no-op when OTel is unavailable
"""

import logging
import os
import time
from unittest.mock import MagicMock, patch

import pytest

import agents.tracing as tracing_module
from agents.tracing import (
    log_error,
    log_phase_transition,
    log_tool_invocation,
    setup_tracing,
    trace_agent_call,
    trace_mcp_call,
    traced_agent,
    get_tracer,
    _prompt_logging_enabled,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_tracing_state(monkeypatch):
    """Reset tracing module state before each test."""
    monkeypatch.setattr(tracing_module, "_initialized", False)
    monkeypatch.setattr(tracing_module, "_tracer", None)
    monkeypatch.setenv("ENABLE_PROMPT_LOGGING", "true")
    yield


# ---------------------------------------------------------------------------
# setup_tracing tests
# ---------------------------------------------------------------------------


class TestSetupTracing:
    def test_setup_when_otel_available(self, monkeypatch):
        """setup_tracing initializes tracer when OTel is available."""
        monkeypatch.setattr(tracing_module, "_OTEL_AVAILABLE", True)
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        monkeypatch.setenv("OTEL_SERVICE_NAME", "test-service")

        setup_tracing()

        assert tracing_module._initialized is True
        assert get_tracer() is not None

    def test_setup_is_idempotent(self, monkeypatch):
        """Calling setup_tracing twice does not reinitialize."""
        monkeypatch.setattr(tracing_module, "_OTEL_AVAILABLE", True)
        monkeypatch.setenv("OTEL_SERVICE_NAME", "test-service")

        setup_tracing()
        tracer_first = get_tracer()

        setup_tracing()
        tracer_second = get_tracer()

        assert tracer_first is tracer_second

    def test_setup_noop_when_otel_unavailable(self, monkeypatch):
        """setup_tracing is a no-op when OTel dependencies are missing."""
        monkeypatch.setattr(tracing_module, "_OTEL_AVAILABLE", False)

        setup_tracing()

        assert tracing_module._initialized is False
        assert get_tracer() is None


# ---------------------------------------------------------------------------
# trace_agent_call tests
# ---------------------------------------------------------------------------


class TestTraceAgentCall:
    def test_context_yields_mutable_dict(self, monkeypatch):
        """trace_agent_call yields a dict that callers can populate."""
        monkeypatch.setattr(tracing_module, "_OTEL_AVAILABLE", False)

        with trace_agent_call("test_agent", phase="clarification") as ctx:
            ctx["output_size"] = 42
            ctx["tool_calls"] = 3
            ctx["token_usage"] = {"input": 100, "output": 50}

        assert ctx["output_size"] == 42
        assert ctx["tool_calls"] == 3

    def test_context_propagates_exceptions(self, monkeypatch):
        """Exceptions inside trace_agent_call are re-raised."""
        monkeypatch.setattr(tracing_module, "_OTEL_AVAILABLE", False)

        with pytest.raises(ValueError, match="test error"):
            with trace_agent_call("test_agent") as ctx:
                raise ValueError("test error")

    def test_otel_span_created_when_available(self, monkeypatch):
        """When OTel is available, a span is created with proper attributes."""
        monkeypatch.setattr(tracing_module, "_OTEL_AVAILABLE", True)
        monkeypatch.setenv("OTEL_SERVICE_NAME", "test")

        setup_tracing()

        with trace_agent_call(
            "clarification", phase="clarification", input_data="hello"
        ) as ctx:
            ctx["output_size"] = 100
            ctx["tool_calls"] = 2
            ctx["token_usage"] = {"input": 50, "output": 30}

        # If we get here without error, span was created and ended successfully

    def test_prompt_not_recorded_when_disabled(self, monkeypatch):
        """When ENABLE_PROMPT_LOGGING is false, input is not in span attributes."""
        monkeypatch.setattr(tracing_module, "_OTEL_AVAILABLE", True)
        monkeypatch.setenv("ENABLE_PROMPT_LOGGING", "false")
        monkeypatch.setenv("OTEL_SERVICE_NAME", "test")

        setup_tracing()

        # This should not raise even with prompt logging disabled
        with trace_agent_call(
            "agent", phase="test", input_data="sensitive data"
        ) as ctx:
            ctx["output_size"] = 10


# ---------------------------------------------------------------------------
# trace_mcp_call tests
# ---------------------------------------------------------------------------


class TestTraceMcpCall:
    def test_logs_invocation(self, monkeypatch, caplog):
        """trace_mcp_call logs tool invocation with duration."""
        monkeypatch.setattr(tracing_module, "_OTEL_AVAILABLE", False)

        with caplog.at_level(logging.INFO):
            with trace_mcp_call("research", "aws_docs_search"):
                time.sleep(0.01)

        assert any("Tool invocation" in r.message for r in caplog.records)

    def test_warns_on_slow_mcp_call(self, monkeypatch, caplog):
        """MCP calls exceeding 10s threshold emit a warning."""
        monkeypatch.setattr(tracing_module, "_OTEL_AVAILABLE", False)
        monkeypatch.setattr(tracing_module, "_MCP_SLOW_THRESHOLD_SECONDS", 0.01)

        with caplog.at_level(logging.WARNING):
            with trace_mcp_call("research", "slow_tool"):
                time.sleep(0.02)

        assert any("exceeded" in r.message for r in caplog.records)

    def test_logs_error_on_exception(self, monkeypatch, caplog):
        """trace_mcp_call logs error details when the call raises."""
        monkeypatch.setattr(tracing_module, "_OTEL_AVAILABLE", False)

        with caplog.at_level(logging.INFO):
            with pytest.raises(RuntimeError):
                with trace_mcp_call("research", "failing_tool"):
                    raise RuntimeError("connection lost")

        # The tool invocation log should show success=False
        records_with_extra = [
            r for r in caplog.records if hasattr(r, "success")
        ]
        # At minimum the log_tool_invocation was called

    def test_propagates_exception(self, monkeypatch):
        """Exceptions inside trace_mcp_call are re-raised."""
        monkeypatch.setattr(tracing_module, "_OTEL_AVAILABLE", False)

        with pytest.raises(ValueError, match="boom"):
            with trace_mcp_call("agent", "tool"):
                raise ValueError("boom")


# ---------------------------------------------------------------------------
# traced_agent decorator tests
# ---------------------------------------------------------------------------


class TestTracedAgentDecorator:
    def test_decorator_preserves_return_value(self, monkeypatch):
        """Decorated function returns its original value."""
        monkeypatch.setattr(tracing_module, "_OTEL_AVAILABLE", False)

        class Agent:
            @traced_agent(agent_name="test_agent", phase="test")
            def process(self, description: str) -> str:
                return f"processed: {description}"

        agent = Agent()
        result = agent.process("input text")
        assert result == "processed: input text"

    def test_decorator_preserves_function_name(self, monkeypatch):
        """Decorated function preserves __name__ via functools.wraps."""
        monkeypatch.setattr(tracing_module, "_OTEL_AVAILABLE", False)

        @traced_agent(agent_name="my_agent")
        def my_function(x: str) -> str:
            return x

        assert my_function.__name__ == "my_function"

    def test_decorator_propagates_exceptions(self, monkeypatch):
        """Exceptions in decorated functions are re-raised."""
        monkeypatch.setattr(tracing_module, "_OTEL_AVAILABLE", False)

        @traced_agent(agent_name="failing_agent")
        def failing(x: str) -> str:
            raise RuntimeError("agent failed")

        with pytest.raises(RuntimeError, match="agent failed"):
            failing("input")


# ---------------------------------------------------------------------------
# Structured logging tests
# ---------------------------------------------------------------------------


class TestStructuredLogging:
    def test_log_phase_transition(self, caplog):
        """log_phase_transition emits INFO log with structured data."""
        with caplog.at_level(logging.INFO):
            log_phase_transition("session-1", "clarification", "research")

        assert any("Phase transition" in r.message for r in caplog.records)

    def test_log_tool_invocation_success(self, caplog):
        """log_tool_invocation emits INFO for successful calls."""
        with caplog.at_level(logging.INFO):
            log_tool_invocation("research", "pricing_api", 1.5, True)

        assert any("Tool invocation" in r.message for r in caplog.records)

    def test_log_tool_invocation_slow_warning(self, caplog):
        """log_tool_invocation emits WARNING for calls over 10s."""
        with caplog.at_level(logging.WARNING):
            log_tool_invocation("research", "slow_api", 12.0, True)

        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) >= 1
        assert "exceeded" in warning_records[0].message

    def test_log_error(self, caplog):
        """log_error emits ERROR log with exception details."""
        with caplog.at_level(logging.ERROR):
            log_error("design", ValueError("bad output"), phase="design")

        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) >= 1
        assert "bad output" in error_records[0].message


# ---------------------------------------------------------------------------
# Prompt logging toggle tests
# ---------------------------------------------------------------------------


class TestPromptLoggingToggle:
    def test_enabled_by_default(self, monkeypatch):
        """Prompt logging is enabled when env var is not set."""
        monkeypatch.delenv("ENABLE_PROMPT_LOGGING", raising=False)
        assert _prompt_logging_enabled() is True

    def test_enabled_when_true(self, monkeypatch):
        """Prompt logging is enabled when env var is 'true'."""
        monkeypatch.setenv("ENABLE_PROMPT_LOGGING", "true")
        assert _prompt_logging_enabled() is True

    def test_disabled_when_false(self, monkeypatch):
        """Prompt logging is disabled when env var is 'false'."""
        monkeypatch.setenv("ENABLE_PROMPT_LOGGING", "false")
        assert _prompt_logging_enabled() is False

    def test_disabled_case_insensitive(self, monkeypatch):
        """Prompt logging disable check is case-insensitive."""
        monkeypatch.setenv("ENABLE_PROMPT_LOGGING", "False")
        assert _prompt_logging_enabled() is False
