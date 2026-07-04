"""Research Agent — live AWS research via MCP tools.

A Strands Agent equipped with the AWS Documentation and AWS Pricing MCP
servers as tools. The agent decides which tools to call (doc lookups,
pricing queries) and returns a structured ResearchSummary. When MCP servers
are not configured, the agent still runs — it researches from model
knowledge and flags `data_sources_available=false` so downstream output is
honest about pricing being estimates.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from models.requirements import RequirementsProfile
from models.research import ResearchSummary

logger = logging.getLogger(__name__)

# Hard budget on agent-loop turns (1 turn = 1 model call + its tool calls).
# Uncapped MCP research was observed taking 3-4+ minutes of sequential doc
# fetches — unacceptable in a live demo. Tune via RESEARCH_MAX_TURNS.
DEFAULT_MAX_TURNS = 6

RESEARCH_SYSTEM_PROMPT = """You are an AWS research analyst preparing inputs for an architecture design.

Given a RequirementsProfile, produce a ResearchSummary:
- reference_architectures: 2-4 AWS reference architectures genuinely relevant to this workload, each with why it applies.
- service_recommendations: the candidate services for this workload with justification, real alternatives, pricing summary, and free-tier eligibility.
- well_architected_guidance: per-pillar recommendations and risks specific to this workload.
- pricing_comparisons: cost comparisons between the real alternatives (compute, database, storage), with monthly estimates derived from the profile's traffic and storage numbers.

If you have MCP tools available (AWS documentation search, AWS pricing), USE them for current documentation and prices, and set data_sources_available=true. If you have no tools, research from your own knowledge, set data_sources_available=false, and add a note that pricing figures are estimates.

Return ONLY the structured ResearchSummary. Keep any commentary between tool calls to one short sentence per step."""


class ResearchAgent:
    """AWS research agent backed by Strands with optional MCP tools."""

    def __init__(
        self,
        model: Any,
        docs_mcp: Any | None = None,
        pricing_mcp: Any | None = None,
    ):
        from strands import Agent

        self._mcp_clients = [c for c in (docs_mcp, pricing_mcp) if c is not None]
        tools: list[Any] = list(self._mcp_clients)
        self._agent = Agent(
            model=model,
            system_prompt=RESEARCH_SYSTEM_PROMPT,
            tools=tools or None,
        )

    def research(self, profile: RequirementsProfile) -> ResearchSummary:
        """Research reference architectures, services, and pricing for the profile."""
        max_turns = int(os.environ.get("RESEARCH_MAX_TURNS", str(DEFAULT_MAX_TURNS)))
        prompt = (
            f"## Requirements Profile\n{profile.model_dump_json(indent=2)}\n\n"
            "Produce the ResearchSummary for this workload. You have a tight "
            f"tool budget (~{max(max_turns - 2, 1)} tool calls): spend it on "
            "pricing for the main compute and database choices, and fill the "
            "rest from your own knowledge."
        )
        agent_result = self._agent(
            prompt,
            structured_output_model=ResearchSummary,
            limits={"turns": max_turns},
        )
        result: ResearchSummary | None = agent_result.structured_output
        if result is None:
            # Budget fired before the final answer — the tool results are in
            # conversation memory; force a tool-free synthesis pass.
            result = self._agent(
                "Tool budget exhausted. Produce the final ResearchSummary NOW "
                "from what you have gathered so far.",
                structured_output_model=ResearchSummary,
                limits={"turns": 2},
            ).structured_output

        if not self._mcp_clients:
            result.data_sources_available = False
            note = "No MCP data sources configured — pricing figures are model estimates."
            if note not in result.notes:
                result.notes.append(note)
        return result
