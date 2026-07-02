"""Custom exception hierarchy for AWS Architect AI."""


class ArchitectAIError(Exception):
    """Base exception for the application."""

    pass


class BedrockConnectionError(ArchitectAIError):
    """Failed to connect to Amazon Bedrock."""

    pass


class BedrockThrottlingError(ArchitectAIError):
    """Request was throttled by AWS."""

    pass


class BedrockTimeoutError(ArchitectAIError):
    """Request exceeded timeout."""

    pass


class JsonExtractionError(ArchitectAIError):
    """No valid JSON found in response."""

    pass


class DiagramRenderError(ArchitectAIError):
    """Diagram rendering failed."""

    pass


class ConfigurationError(ArchitectAIError):
    """Required configuration is missing."""

    pass
