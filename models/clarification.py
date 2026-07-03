"""Data models for the clarification phase."""

from pydantic import BaseModel, Field

from models.requirements import RequirementsProfile


class ClarifyingQuestion(BaseModel):
    """A single clarifying question with a suggested default."""

    question: str
    category: str = Field(
        description="compute, budget, compliance, traffic, storage, auth, ha, dr"
    )
    suggested_default: str | None = None


class ClarificationResult(BaseModel):
    """Output from a clarification round."""

    questions: list[ClarifyingQuestion] = Field(default_factory=list)
    profile: RequirementsProfile | None = None
    is_complete: bool = False
    round_number: int = 1
