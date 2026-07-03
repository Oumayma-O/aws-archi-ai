"""Data models for session state and workflow management."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

import uuid

from pydantic import BaseModel, Field

from models.requirements import RequirementsProfile
from models.research import ResearchSummary


class WorkflowPhase(str, Enum):
    """Phases of the agentic architecture workflow."""

    REQUIREMENTS_ANALYSIS = "requirements_analysis"
    CLARIFICATION = "clarification"
    RESEARCH = "research"
    DESIGN = "design"
    DIAGRAM_GENERATION = "diagram_generation"
    REVIEW = "review"
    FINAL_REPORT = "final_report"
    COMPLETE = "complete"


class ConversationMessage(BaseModel):
    """A single message in the conversation history."""

    role: str = Field(description="'user' or 'assistant'")
    content: str = Field(description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    phase: WorkflowPhase | None = None
    artifacts: list[str] = Field(default_factory=list)


class Session(BaseModel):
    """Complete session state persisted across turns."""

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(default="default")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    current_phase: WorkflowPhase = WorkflowPhase.REQUIREMENTS_ANALYSIS
    conversation_history: list[ConversationMessage] = Field(
        default_factory=list
    )
    requirements_profile: RequirementsProfile | None = None
    research_summary: ResearchSummary | None = None
    architecture_report: Any | None = Field(
        default=None,
        description="ArchitectureReport instance (typed as Any until models/report.py is created)",
    )
    clarification_rounds: int = 0
    is_complete: bool = False
