"""Shared Bedrock model factory for LLM-backed agents.

Every sub-agent (Clarification, Design, Research, Diagram) accepts an
optional Strands ``model`` and degrades to deterministic logic when it is
``None``. Previously the orchestrator always passed ``model=None``, so the
deterministic fallback was the *only* path ever exercised. This module
builds the real model so the LLM path becomes reachable; ``None`` is now
reserved for genuine outages (missing credentials, Strands unavailable) and
for unit tests that want the deterministic path on purpose.

Two factories:
- ``create_model(model_id)`` — the user-selected model (sidebar), used for
  the quality-critical design and review work.
- ``create_fast_model()`` — Haiku pinned, used for clarification and
  research: extraction/lookup tasks where latency matters more than depth.

Both enable automatic prompt caching (the clarification agent's
conversation grows every round; caching makes rounds 2+ reuse the prefix).
Schema-violation retry turns are mitigated by tolerant Pydantic validators
on the output models instead of Bedrock's strict-tools flag, which the
eu-west-1 Converse API rejects.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MODEL_ID = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
FAST_MODEL_ID = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
DEFAULT_TEMPERATURE = 0.3


def create_model(model_id: str | None = None, region: str | None = None) -> Any | None:
    """Create a BedrockModel for agent use.

    Args:
        model_id: Bedrock model identifier. Defaults to BEDROCK_MODEL_ID env
            var, then DEFAULT_MODEL_ID. Lets the UI's model selector
            (Haiku/Sonnet) flow through to the agents.
        region: AWS region. Defaults to AWS_REGION env var, then eu-west-1.

    Returns:
        A configured strands.models.BedrockModel, or None if the Strands
        Bedrock integration is unavailable or construction fails. Callers
        must treat None as "run the deterministic fallback".
    """
    try:
        from strands.models.bedrock import BedrockModel, CacheConfig
    except ImportError as exc:
        logger.warning(
            "Strands BedrockModel unavailable (%s); agents will run in "
            "deterministic fallback mode.",
            exc,
        )
        return None

    resolved_model_id = model_id or os.environ.get("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)
    resolved_region = region or os.environ.get("AWS_REGION", "eu-west-1")

    try:
        # NOTE: strict_tools is deliberately NOT enabled — the eu-west-1
        # Bedrock Converse API rejects the "strict" toolSpec parameter
        # ("Unknown parameter in toolConfig.tools[0].toolSpec"). Schema
        # tolerance is handled model-side instead (see the None-coercing
        # validator on ClarifyingQuestion.options).
        return BedrockModel(
            model_id=resolved_model_id,
            region_name=resolved_region,
            temperature=DEFAULT_TEMPERATURE,
            cache_config=CacheConfig(strategy="auto"),
        )
    except Exception as exc:
        logger.warning(
            "Failed to construct BedrockModel (%s); falling back to "
            "deterministic mode.",
            exc,
        )
        return None


def create_fast_model(region: str | None = None) -> Any | None:
    """Create the latency-optimized Haiku model for clarification/research.

    Overridable via BEDROCK_FAST_MODEL_ID. Returns None on failure — the
    orchestrator falls back to the main model in that case.
    """
    fast_id = os.environ.get("BEDROCK_FAST_MODEL_ID", FAST_MODEL_ID)
    return create_model(model_id=fast_id, region=region)
