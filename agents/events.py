"""Agent Events module.

Defines the event types streamed from agents to the Streamlit UI during
workflow execution. Events enable real-time streaming of text, phase
transitions, artifacts, and errors.

Responsibilities:
- Define AgentEventType enum for event classification
- Define AgentEvent model for structured event streaming
- Support TEXT_CHUNK, PHASE_TRANSITION, ARTIFACT, TOOL_CALL, ERROR, COMPLETE events
"""

from enum import Enum

from pydantic import BaseModel


class AgentEventType(str, Enum):
    """Types of events emitted during agent execution."""

    TEXT_CHUNK = "text_chunk"
    PHASE_TRANSITION = "phase_transition"
    ARTIFACT = "artifact"
    TOOL_CALL = "tool_call"
    ERROR = "error"
    COMPLETE = "complete"


class AgentEvent(BaseModel):
    """Event emitted during agent execution for UI streaming."""

    type: AgentEventType
    data: str | dict
    phase: str | None = None
    timestamp: float
