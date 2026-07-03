"""OpenTelemetry tracing module for the Agentic Architect.

Provides observability via OTel traces exported to AWS X-Ray and structured
CloudWatch Logs for agent invocations, phase transitions, tool calls, and errors.

This module is OPTIONAL — if OpenTelemetry dependencies are not installed, all
exports become no-ops so the rest of the system functions normally without tracing.

Environment Variables:
    OTEL_EXPORTER_OTLP_ENDPOINT: OTLP collector endpoint (default: http://localhost:4317)
    OTEL_SERVICE_NAME: Service name for traces (default: agentic-architect)
    ENABLE_PROMPT_LOGGING: Set to "false" to suppress prompt/response recording
        in trace spans (recommended for production to reduce cost/privacy exposure)

Requirements: 11.1, 11.2, 11.3, 11.5, 11.6
"""

from __future__ import annotations

import functools
import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Callable, Generator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Attempt to import OpenTelemetry — graceful no-op if unavailable
# ---------------------------------------------------------------------------

_OTEL_AVAILABLE = False

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.trace import StatusCode

    _OTEL_AVAILABLE = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_ENDPOINT = "http://localhost:4317"
_DEFAULT_SERVICE_NAME = "agentic-architect"
_MCP_SLOW_THRESHOLD_SECONDS = 10.0

_tracer: Any = None
_initialized = False


def _prompt_logging_enabled() -> bool:
    """Check if prompt/response logging is enabled (defaults to True)."""
    return os.environ.get("ENABLE_PROMPT_LOGGING", "true").lower() != "false"


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


def setup_tracing() -> None:
    """Configure OpenTelemetry tracing with X-Ray as the backend.

    Reads OTEL_EXPORTER_OTLP_ENDPOINT and OTEL_SERVICE_NAME from environment.
    If OTel dependencies are not installed, this is a no-op.

    Should be called once at application startup.
    """
    global _tracer, _initialized

    if not _OTEL_AVAILABLE:
        logger.info("OpenTelemetry dependencies not available — tracing disabled")
        return

    if _initialized:
        return

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", _DEFAULT_ENDPOINT)
    service_name = os.environ.get("OTEL_SERVICE_NAME", _DEFAULT_SERVICE_NAME)

    resource = Resource.create(
        {
            "service.name": service_name,
            "cloud.provider": "aws",
        }
    )

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(service_name)
    _initialized = True

    logger.info(
        "OpenTelemetry tracing configured",
        extra={
            "otel_endpoint": endpoint,
            "service_name": service_name,
            "prompt_logging": _prompt_logging_enabled(),
        },
    )


def get_tracer() -> Any:
    """Return the configured tracer, or None if tracing is unavailable."""
    return _tracer


# ---------------------------------------------------------------------------
# Structured logging helpers
# ---------------------------------------------------------------------------


def log_phase_transition(session_id: str, from_phase: str, to_phase: str) -> None:
    """Emit a structured CloudWatch log for a workflow phase transition.

    Args:
        session_id: The active session identifier.
        from_phase: The phase being exited.
        to_phase: The phase being entered.
    """
    logger.info(
        "Phase transition",
        extra={
            "event_type": "phase_transition",
            "session_id": session_id,
            "from_phase": from_phase,
            "to_phase": to_phase,
            "timestamp": time.time(),
        },
    )


def log_tool_invocation(
    agent_name: str,
    tool_name: str,
    duration_seconds: float,
    success: bool,
    error: str | None = None,
) -> None:
    """Emit a structured CloudWatch log for a tool invocation.

    Also logs a warning if the MCP call exceeds the 10-second threshold.

    Args:
        agent_name: Name of the agent that invoked the tool.
        tool_name: Name of the tool/MCP server called.
        duration_seconds: How long the call took.
        success: Whether the call succeeded.
        error: Error message if the call failed.
    """
    log_data: dict[str, Any] = {
        "event_type": "tool_invocation",
        "agent_name": agent_name,
        "tool_name": tool_name,
        "duration_seconds": round(duration_seconds, 3),
        "success": success,
        "timestamp": time.time(),
    }
    if error:
        log_data["error"] = error

    if duration_seconds > _MCP_SLOW_THRESHOLD_SECONDS:
        logger.warning(
            "MCP call exceeded %ss threshold: %s took %.2fs",
            _MCP_SLOW_THRESHOLD_SECONDS,
            tool_name,
            duration_seconds,
            extra=log_data,
        )
    else:
        logger.info("Tool invocation", extra=log_data)


def log_error(agent_name: str, error: Exception, phase: str | None = None) -> None:
    """Emit a structured CloudWatch log for an agent error.

    Args:
        agent_name: Name of the agent that encountered the error.
        error: The exception that occurred.
        phase: The workflow phase during which the error occurred.
    """
    logger.error(
        "Agent error: %s",
        str(error),
        extra={
            "event_type": "agent_error",
            "agent_name": agent_name,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "phase": phase,
            "timestamp": time.time(),
        },
    )


# ---------------------------------------------------------------------------
# Trace context manager for agent calls
# ---------------------------------------------------------------------------


@contextmanager
def trace_agent_call(
    agent_name: str,
    phase: str | None = None,
    input_data: str | None = None,
) -> Generator[dict[str, Any], None, None]:
    """Context manager that wraps an agent invocation in an OTel trace span.

    Creates a span with attributes for agent name, phase, input/output sizes,
    duration, and optionally the prompt content (if ENABLE_PROMPT_LOGGING is true).

    Usage:
        with trace_agent_call("clarification", phase="clarification", input_data=msg) as span_ctx:
            result = agent.analyze_and_clarify(description)
            span_ctx["output_size"] = len(str(result))
            span_ctx["tool_calls"] = 3
            span_ctx["token_usage"] = {"input": 500, "output": 200}

    Args:
        agent_name: Name of the agent being invoked.
        phase: Current workflow phase.
        input_data: The input prompt/message (recorded only if prompt logging enabled).

    Yields:
        A mutable dict where callers can set additional span attributes:
            - output_size (int)
            - tool_calls (int)
            - token_usage (dict with "input" and "output" keys)
            - error (str)
    """
    span_ctx: dict[str, Any] = {
        "output_size": 0,
        "tool_calls": 0,
        "token_usage": {},
    }
    start_time = time.time()

    if not _OTEL_AVAILABLE or _tracer is None:
        # No-op path: just yield the context dict for callers to populate
        try:
            yield span_ctx
        finally:
            duration = time.time() - start_time
            logger.debug(
                "Agent call completed (tracing disabled): %s in %.2fs",
                agent_name,
                duration,
            )
        return

    # OTel-instrumented path
    with _tracer.start_as_current_span(f"agent.{agent_name}") as span:
        span.set_attribute("agent.name", agent_name)
        if phase:
            span.set_attribute("agent.phase", phase)
        if input_data:
            span.set_attribute("agent.input_size", len(input_data))
            if _prompt_logging_enabled():
                span.set_attribute("agent.input", input_data[:4096])

        try:
            yield span_ctx
        except Exception as exc:
            span.set_status(StatusCode.ERROR, str(exc))
            span.set_attribute("agent.error", str(exc))
            span.set_attribute("agent.error_type", type(exc).__name__)
            log_error(agent_name, exc, phase=phase)
            raise
        finally:
            duration = time.time() - start_time
            span.set_attribute("agent.duration_seconds", round(duration, 3))
            span.set_attribute("agent.output_size", span_ctx.get("output_size", 0))
            span.set_attribute("agent.tool_calls", span_ctx.get("tool_calls", 0))

            token_usage = span_ctx.get("token_usage", {})
            if token_usage:
                span.set_attribute(
                    "agent.token_usage.input", token_usage.get("input", 0)
                )
                span.set_attribute(
                    "agent.token_usage.output", token_usage.get("output", 0)
                )

            if span_ctx.get("output_size") and _prompt_logging_enabled():
                output_preview = span_ctx.get("output_preview", "")
                if output_preview:
                    span.set_attribute("agent.output", output_preview[:4096])


# ---------------------------------------------------------------------------
# Decorator for agent methods
# ---------------------------------------------------------------------------


def traced_agent(
    agent_name: str | None = None, phase: str | None = None
) -> Callable:
    """Decorator that wraps an agent method with OTel tracing.

    Can be applied to synchronous agent methods. The decorated function's
    first string argument (after self) is treated as the input for span sizing.

    Args:
        agent_name: Override agent name (defaults to function name).
        phase: Override phase name.

    Returns:
        Decorator function.

    Usage:
        @traced_agent(agent_name="clarification", phase="clarification")
        def analyze_and_clarify(self, description: str, ...):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            name = agent_name or func.__name__
            # Try to extract input from the first non-self argument
            input_data = None
            func_args = args[1:] if args else args  # skip 'self' if present
            if func_args and isinstance(func_args[0], str):
                input_data = func_args[0]

            with trace_agent_call(name, phase=phase, input_data=input_data) as ctx:
                result = func(*args, **kwargs)
                if result is not None:
                    ctx["output_size"] = len(str(result))
                return result

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# MCP call timing helper
# ---------------------------------------------------------------------------


@contextmanager
def trace_mcp_call(
    agent_name: str, tool_name: str
) -> Generator[None, None, None]:
    """Context manager to time and trace an MCP tool call.

    Logs the invocation and warns if the call exceeds 10 seconds.

    Args:
        agent_name: Name of the agent making the call.
        tool_name: Name of the MCP tool being invoked.

    Yields:
        None — callers just wrap their MCP call in this context.

    Usage:
        with trace_mcp_call("research", "aws_docs_search"):
            result = mcp_client.call("search", params)
    """
    start = time.time()
    span = None
    success = True
    error_msg = None

    if _OTEL_AVAILABLE and _tracer is not None:
        span = _tracer.start_span(f"mcp.{tool_name}")
        span.set_attribute("mcp.tool_name", tool_name)
        span.set_attribute("mcp.agent_name", agent_name)

    try:
        yield
    except Exception as exc:
        success = False
        error_msg = str(exc)
        if span:
            span.set_status(StatusCode.ERROR, error_msg)
            span.set_attribute("mcp.error", error_msg)
        raise
    finally:
        duration = time.time() - start
        if span:
            span.set_attribute("mcp.duration_seconds", round(duration, 3))
            span.end()
        log_tool_invocation(
            agent_name=agent_name,
            tool_name=tool_name,
            duration_seconds=duration,
            success=success,
            error=error_msg,
        )
