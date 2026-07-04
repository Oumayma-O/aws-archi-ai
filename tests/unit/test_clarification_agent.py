"""Unit tests for the ClarificationAgent.

The agent is a thin wrapper over a Strands Agent with structured output:
these tests mock the underlying Agent and verify the wrapper's contract —
prompt construction (skip finalization, round-pressure hints), round-number
stamping, and profile backstopping. Real question quality is exercised by
integration tests against Bedrock.
"""

from unittest.mock import MagicMock, patch

import pytest

from agents.clarification import MAX_CLARIFICATION_ROUNDS, ClarificationAgent
from models.clarification import ClarificationResult, ClarifyingQuestion
from models.requirements import RequirementsProfile


def _make_agent(returned: ClarificationResult) -> tuple[ClarificationAgent, MagicMock]:
    """Build a ClarificationAgent whose inner Strands Agent is mocked."""
    with patch("strands.Agent") as agent_cls:
        inner = MagicMock()
        inner.return_value.structured_output = returned
        agent_cls.return_value = inner
        agent = ClarificationAgent(model=MagicMock())
    return agent, inner


@pytest.fixture
def incomplete_result() -> ClarificationResult:
    return ClarificationResult(
        questions=[
            ClarifyingQuestion(
                question="What is your monthly budget?",
                category="budget",
                suggested_default="500",
                options=["< $100", "$100-500"],
            )
        ],
        profile=RequirementsProfile(original_description="a web app"),
        is_complete=False,
    )


@pytest.fixture
def complete_result() -> ClarificationResult:
    return ClarificationResult(
        questions=[],
        profile=RequirementsProfile(
            original_description="a web app", compute_preference="serverless"
        ),
        is_complete=True,
    )


class TestAnalyzeAndClarify:
    def test_passes_description_through_and_stamps_round(self, incomplete_result):
        agent, inner = _make_agent(incomplete_result)
        result = agent.analyze_and_clarify("Build me a web app", round_number=1)

        prompt = inner.call_args.args[0]
        assert prompt == "Build me a web app"
        assert inner.call_args.kwargs["structured_output_model"] is ClarificationResult
        assert result.round_number == 1
        assert result.questions[0].category == "budget"

    def test_round_two_adds_batching_pressure(self, incomplete_result):
        agent, inner = _make_agent(incomplete_result)
        agent.analyze_and_clarify("budget: 500", round_number=2)
        assert "batch every remaining category" in inner.call_args.args[0]

    def test_last_round_adds_finish_pressure(self, incomplete_result):
        agent, inner = _make_agent(incomplete_result)
        agent.analyze_and_clarify("some answer", round_number=MAX_CLARIFICATION_ROUNDS - 1)
        assert "last chance" in inner.call_args.args[0]

    @pytest.mark.parametrize(
        "text",
        ["skip", "just generate", "go ahead", "use defaults", "don't ask",
         "no more questions", "proceed"],
    )
    def test_skip_intent_requests_finalization(self, complete_result, text):
        agent, inner = _make_agent(complete_result)
        agent.analyze_and_clarify(text, round_number=2)
        assert "Finalize NOW" in inner.call_args.args[0]

    def test_normal_text_does_not_request_finalization(self, incomplete_result):
        agent, inner = _make_agent(incomplete_result)
        agent.analyze_and_clarify("I need a web app with a product catalog", round_number=1)
        assert "Finalize NOW" not in inner.call_args.args[0]

    def test_exceeding_max_rounds_requests_finalization(self, complete_result):
        agent, inner = _make_agent(complete_result)
        result = agent.analyze_and_clarify("more info", round_number=MAX_CLARIFICATION_ROUNDS + 1)
        assert "Finalize NOW" in inner.call_args.args[0]
        assert result.round_number == MAX_CLARIFICATION_ROUNDS

    def test_missing_profile_is_backstopped(self):
        no_profile = ClarificationResult(questions=[], profile=None, is_complete=True)
        agent, _ = _make_agent(no_profile)
        existing = RequirementsProfile(
            original_description="existing", compute_preference="containers"
        )
        result = agent.analyze_and_clarify("go ahead", existing_profile=existing, round_number=3)
        assert result.profile is existing

    def test_missing_profile_without_existing_creates_one(self):
        no_profile = ClarificationResult(questions=[], profile=None, is_complete=True)
        agent, _ = _make_agent(no_profile)
        result = agent.analyze_and_clarify("build an API", round_number=1)
        assert result.profile is not None
        assert result.profile.original_description == "build an API"

    def test_llm_error_propagates(self):
        agent, inner = _make_agent(ClarificationResult())
        inner.side_effect = RuntimeError("bedrock down")
        with pytest.raises(RuntimeError):
            agent.analyze_and_clarify("build an API", round_number=1)
