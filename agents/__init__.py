"""Agentic Architect package.

This package contains the multi-turn conversational AWS Solutions Architect
powered by Strands Agents SDK. It implements an agents-as-tools orchestration
pattern where a top-level Orchestrator Agent delegates to specialized sub-agents.

Dependency rule: pages/ → agents/ → services/ → models/
This module may import from services/ and models/ but NEVER from pages/.

Public API:
    OrchestratorAgent — Top-level workflow orchestrator
    AgentEvent — Streaming event model emitted during execution
    AgentEventType — Enum classifying event types
    Session — Persistent session state model
    WorkflowPhase — Enum of workflow phases
    create_architect_agent — Factory function for UI consumption
"""

from __future__ import annotations

from agents.events import AgentEvent, AgentEventType
from agents.orchestrator import OrchestratorAgent
from models.session import Session, WorkflowPhase

__all__ = [
    "OrchestratorAgent",
    "AgentEvent",
    "AgentEventType",
    "Session",
    "WorkflowPhase",
    "create_architect_agent",
]


def create_architect_agent(session_id: str | None = None) -> OrchestratorAgent:
    """Create a fully-initialized OrchestratorAgent ready for UI consumption.

    Initialization order:
        1. MCP clients (docs, pricing, draw.io) — configured from environment
        2. OrchestratorAgent with optional session resumption

    The MCP clients are initialized first so that if any fail (missing deps,
    server unavailable), the agent still starts with graceful degradation.

    Args:
        session_id: Optional existing session ID to resume a prior conversation.
            If None, a new session is created.

    Returns:
        A configured OrchestratorAgent instance ready to process user messages.
    """
    from agents import mcp_config

    # Step 1: Initialize MCP clients (failures are non-blocking)
    mcp_config.create_docs_mcp()
    mcp_config.create_pricing_mcp()
    mcp_config.create_drawio_mcp()

    # Step 2: Create and return the orchestrator agent
    return OrchestratorAgent(session_id=session_id)
