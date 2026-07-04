"""Unit tests for the ResearchAgent.

The agent delegates research to a Strands Agent (optionally armed with AWS
docs/pricing MCP tools) and returns a structured ResearchSummary. These
tests mock the inner agent and verify tool wiring and the honesty flag when
no MCP data sources are configured.
"""

from unittest.mock import MagicMock, patch

import pytest

from agents.research import ResearchAgent
from models.requirements import RequirementsProfile
from models.research import ResearchSummary


@pytest.fixture
def profile() -> RequirementsProfile:
    return RequirementsProfile(
        original_description="e-commerce platform",
        compute_preference="serverless",
    )


def _make_agent(returned: ResearchSummary, **kwargs) -> tuple[ResearchAgent, MagicMock, MagicMock]:
    with patch("strands.Agent") as agent_cls:
        inner = MagicMock()
        inner.return_value.structured_output = returned
        agent_cls.return_value = inner
        agent = ResearchAgent(model=MagicMock(), **kwargs)
    return agent, inner, agent_cls


class TestResearchAgent:
    def test_returns_structured_summary(self, profile):
        agent, inner, _ = _make_agent(ResearchSummary(data_sources_available=True))
        result = agent.research(profile)
        assert isinstance(result, ResearchSummary)
        assert inner.call_args.kwargs["structured_output_model"] is ResearchSummary
        assert "e-commerce platform" in inner.call_args.args[0]

    def test_no_mcp_flags_estimates(self, profile):
        agent, _, _ = _make_agent(ResearchSummary(data_sources_available=True))
        result = agent.research(profile)
        assert result.data_sources_available is False
        assert any("estimates" in n for n in result.notes)

    def test_mcp_clients_are_passed_as_tools(self, profile):
        docs = MagicMock(name="docs_mcp")
        pricing = MagicMock(name="pricing_mcp")
        agent, _, agent_cls = _make_agent(
            ResearchSummary(data_sources_available=True),
            docs_mcp=docs,
            pricing_mcp=pricing,
        )
        assert agent_cls.call_args.kwargs["tools"] == [docs, pricing]
        # With data sources wired, the honesty flag is left as the model set it.
        assert agent.research(profile).data_sources_available is True

    def test_partial_mcp_only_includes_present_client(self):
        docs = MagicMock(name="docs_mcp")
        _, _, agent_cls = _make_agent(
            ResearchSummary(), docs_mcp=docs, pricing_mcp=None
        )
        assert agent_cls.call_args.kwargs["tools"] == [docs]

    def test_llm_error_propagates(self, profile):
        agent, inner, _ = _make_agent(ResearchSummary())
        inner.side_effect = RuntimeError("bedrock down")
        with pytest.raises(RuntimeError):
            agent.research(profile)
