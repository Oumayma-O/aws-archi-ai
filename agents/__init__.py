"""Agentic Architect package.

This package contains the multi-turn conversational AWS Solutions Architect
powered by Strands Agents SDK. It implements an agents-as-tools orchestration
pattern where a top-level Orchestrator Agent delegates to specialized sub-agents.

Dependency rule: pages/ → agents/ → services/ → models/
This module may import from services/ and models/ but NEVER from pages/.
"""
