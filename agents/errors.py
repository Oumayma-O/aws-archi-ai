"""Agent Errors module.

Defines the custom exception hierarchy for the agentic layer. All exceptions
inherit from AgenticArchitectError and carry contextual information for
logging and error reporting.

Responsibilities:
- Define base AgenticArchitectError exception
- Define MCPConnectionError for MCP server failures
- Define PhaseFailureError for workflow phase failures
- Define SessionPersistenceError for DynamoDB write failures
- Define AgentTimeoutError for sub-agent timeouts
- Define BedrockConnectionError and BedrockThrottlingError for model API issues
- Define StreamingError for connection interruptions
- Define AgentValidationError for invalid agent output schemas
"""


class AgenticArchitectError(Exception):
    """Base exception for the agentic layer."""

    pass


class MCPConnectionError(AgenticArchitectError):
    """MCP server connection failed."""

    def __init__(self, server_name: str, original_error: Exception):
        self.server_name = server_name
        self.original_error = original_error
        super().__init__(f"MCP server '{server_name}' unavailable: {original_error}")


class PhaseFailureError(AgenticArchitectError):
    """A workflow phase failed after retry."""

    def __init__(self, phase: str, attempts: int, last_error: Exception):
        self.phase = phase
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"Phase '{phase}' failed after {attempts} attempts")


class SessionPersistenceError(AgenticArchitectError):
    """Failed to persist session to DynamoDB."""

    pass


class AgentTimeoutError(AgenticArchitectError):
    """Agent execution exceeded timeout."""

    def __init__(self, agent_name: str, timeout_seconds: int):
        self.agent_name = agent_name
        self.timeout_seconds = timeout_seconds
        super().__init__(f"Agent '{agent_name}' timed out after {timeout_seconds}s")


class BedrockConnectionError(AgenticArchitectError):
    """Bedrock API is unreachable."""

    def __init__(self, original_error: Exception | None = None):
        self.original_error = original_error
        msg = "Unable to connect to Bedrock AI service"
        if original_error:
            msg = f"{msg}: {original_error}"
        super().__init__(msg)


class BedrockThrottlingError(AgenticArchitectError):
    """Bedrock API rate limited."""

    def __init__(self, retry_after_seconds: float | None = None):
        self.retry_after_seconds = retry_after_seconds
        msg = "Bedrock API rate limited"
        if retry_after_seconds is not None:
            msg = f"{msg}, retry after {retry_after_seconds}s"
        super().__init__(msg)


class StreamingError(AgenticArchitectError):
    """Streaming connection interrupted (WebSocket/SSE failure)."""

    def __init__(self, reason: str | None = None, original_error: Exception | None = None):
        self.reason = reason
        self.original_error = original_error
        msg = "Streaming connection interrupted"
        if reason:
            msg = f"{msg}: {reason}"
        super().__init__(msg)


class AgentValidationError(AgenticArchitectError):
    """Invalid agent output schema — agent produced malformed output."""

    def __init__(self, agent_name: str, validation_errors: str | None = None):
        self.agent_name = agent_name
        self.validation_errors = validation_errors
        msg = f"Agent '{agent_name}' produced invalid output"
        if validation_errors:
            msg = f"{msg}: {validation_errors}"
        super().__init__(msg)
