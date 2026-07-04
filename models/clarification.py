"""Data models for the clarification phase."""

from pydantic import BaseModel, Field, field_validator

from models.requirements import RequirementsProfile


class ClarifyingQuestion(BaseModel):
    """A single clarifying question with a suggested default."""

    question: str
    category: str = Field(
        description="compute, budget, compliance, traffic, storage, auth, ha, dr"
    )
    suggested_default: str | None = None
    options: list[str] = Field(
        default_factory=list,
        description=(
            "Multiple-choice options to render as clickable UI choices, chosen "
            "by the agent when the question naturally has a fixed set of "
            "answers. Empty when the question is open-ended (e.g. exact "
            "traffic numbers) — the UI falls back to free text."
        ),
    )

    @field_validator("options", mode="before")
    @classmethod
    def _coerce_none_options(cls, v):
        # Models frequently emit null for "no options"; a hard validation
        # failure here costs a whole extra correction turn (observed live).
        return [] if v is None else v


class ClarificationResult(BaseModel):
    """Output from a clarification round."""

    questions: list[ClarifyingQuestion] = Field(default_factory=list)
    profile: RequirementsProfile | None = None
    is_complete: bool = False
    round_number: int = 1
