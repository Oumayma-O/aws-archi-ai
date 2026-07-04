"""Clarification Agent — conversational requirements gathering.

One persistent Strands Agent per session. Conversation memory is native
(Strands appends every turn to agent.messages), so the model always knows
what has already been asked and answered. Output is constrained to the
ClarificationResult schema via structured output.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from models.clarification import ClarificationResult
from models.requirements import RequirementsProfile

logger = logging.getLogger(__name__)

MAX_CLARIFICATION_ROUNDS = 5

# The UI's "Skip all" button and skip-like chat messages must resolve
# instantly, without an LLM round trip.
_SKIP_RE = re.compile(
    r"\b(skip|just generate|go ahead|use defaults?|don'?t ask|no (more )?questions|proceed)\b",
    re.IGNORECASE,
)

SYSTEM_PROMPT = """You are an expert AWS Solutions Architect conducting a live requirements-gathering interview — the discovery phase of a real client engagement.

You have the full conversation history for this session. Use it as your memory: NEVER re-ask a category already touched anywhere earlier in the conversation, even a brief answer several turns back.

Target TWO rounds total, three at the absolute most. Batch every genuinely-outstanding category into one round rather than trickling questions out. A category is done once the user gives ANY reasonable answer. When in doubt between one more question and a documented assumption, proceed with the assumption.

Every turn:
1. Infer everything you reasonably can from context. "Payment processing" implies PCI-DSS scope — ask "Will you handle card data directly or via a gateway like Stripe?", not a generic compliance question. "5,000 registered users" already implies a traffic ballpark.
2. Only ask about categories genuinely untouched, from: compute, budget, compliance, traffic, storage, auth, ha, dr. Each category appears at most once across the ENTIRE conversation.
3. Every question must be workload-specific with a concrete suggested_default. When a question has a small fixed set of answers, populate `options` with 3-5 clickable choices tailored to the workload; leave `options` empty for open-ended questions.
4. Once every category is covered (answered or safely inferable), set is_complete=true, questions=[], and populate `profile` completely — document every inference or default in `profile.assumptions`.
5. If not complete, return ALL outstanding questions at once, and still populate `profile` with everything known so far so nothing is lost.

Always return a valid, non-null `profile`, complete or partial.
Do not narrate or explain what you are about to do — produce the structured output directly."""


class ClarificationAgent:
    """Requirements-gathering agent backed by a persistent Strands Agent."""

    def __init__(self, model: Any):
        from strands import Agent

        self._agent = Agent(model=model, system_prompt=SYSTEM_PROMPT)

    def analyze_and_clarify(
        self,
        description: str,
        existing_profile: RequirementsProfile | None = None,
        round_number: int = 1,
    ) -> ClarificationResult:
        """Process one turn of the clarification conversation.

        Args:
            description: The user's latest message.
            existing_profile: Last known profile, used only to backstop a
                turn where the model omits one.
            round_number: Owned by the orchestrator; injected into the
                prompt as convergence pressure.
        """
        prompt = description

        if _SKIP_RE.search(description) or round_number > MAX_CLARIFICATION_ROUNDS:
            prompt += (
                "\n\n(Finalize NOW: set is_complete=true, questions=[], and return the "
                "best complete profile you can from the conversation so far, documenting "
                "every assumed default in profile.assumptions.)"
            )
        elif round_number >= MAX_CLARIFICATION_ROUNDS - 1:
            prompt += (
                f"\n\n(Round {round_number} of {MAX_CLARIFICATION_ROUNDS} max — last chance "
                "for questions; prefer finishing now with documented assumptions.)"
            )
        elif round_number >= 2:
            prompt += (
                f"\n\n(Round {round_number} — batch every remaining category now; "
                "do not start another round unless unavoidable.)"
            )

        result: ClarificationResult = self._agent(
            prompt, structured_output_model=ClarificationResult
        ).structured_output

        result.round_number = min(round_number, MAX_CLARIFICATION_ROUNDS)
        if result.profile is None:
            result.profile = existing_profile or RequirementsProfile(
                original_description=description
            )
        return result
