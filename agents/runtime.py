"""AgentCore runtime configuration and fallback logic.

This module handles the decision between running agents on Amazon Bedrock
AgentCore (managed runtime) vs running locally via the Strands SDK on
ECS Fargate.

When AGENTCORE_ENABLED=true and AGENTCORE_ENDPOINT is set, agents connect
to the AgentCore API for managed hosting, scaling, and observability.

When AGENTCORE_ENABLED=false (default for local dev) or AgentCore is
unavailable, agents run locally using the Strands SDK — this is the current
behavior and serves as the fallback.

The actual AgentCore integration will be refined once the AgentCore
Terraform provider and API stabilize. This module provides the switching
logic and configuration loading.
"""

from __future__ import annotations

import logging
import os
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENTCORE_CONFIG_PATH = Path(__file__).resolve().parent.parent / "agentcore" / "config.yaml"


class RuntimeMode(str, Enum):
    """Agent execution runtime mode."""

    LOCAL = "local"  # Strands SDK running locally on ECS Fargate
    AGENTCORE = "agentcore"  # Amazon Bedrock AgentCore managed runtime


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def get_runtime_mode() -> RuntimeMode:
    """Determine the current runtime mode from environment.

    Returns:
        RuntimeMode.AGENTCORE if enabled and endpoint is configured,
        RuntimeMode.LOCAL otherwise.
    """
    enabled = os.environ.get("AGENTCORE_ENABLED", "false").lower() in ("true", "1", "yes")
    endpoint = os.environ.get("AGENTCORE_ENDPOINT", "")

    if enabled and endpoint:
        return RuntimeMode.AGENTCORE
    return RuntimeMode.LOCAL


def get_agentcore_endpoint() -> str | None:
    """Get the AgentCore API endpoint URL.

    Returns:
        The endpoint URL if configured, None otherwise.
    """
    return os.environ.get("AGENTCORE_ENDPOINT") or None


def get_session_table_name() -> str:
    """Get the DynamoDB session table name.

    Returns:
        Table name from environment or default.
    """
    return os.environ.get("SESSION_TABLE_NAME", "architect-sessions")


def load_agentcore_config() -> dict[str, Any]:
    """Load the AgentCore configuration YAML.

    Returns:
        Parsed configuration dictionary. Returns empty dict if file not found.
    """
    if not AGENTCORE_CONFIG_PATH.exists():
        logger.warning("AgentCore config not found at %s", AGENTCORE_CONFIG_PATH)
        return {}

    with open(AGENTCORE_CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    return config or {}


def is_agentcore_available() -> bool:
    """Check if AgentCore is reachable.

    Performs a lightweight health check against the AgentCore endpoint.
    Returns False if the endpoint is not configured or unreachable.

    Returns:
        True if AgentCore is available, False otherwise.
    """
    endpoint = get_agentcore_endpoint()
    if not endpoint:
        return False

    try:
        import urllib.request

        health_url = f"{endpoint.rstrip('/')}/health"
        req = urllib.request.Request(health_url, method="GET")
        req.add_header("Accept", "application/json")

        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status == 200
    except Exception as exc:
        logger.warning("AgentCore health check failed: %s", exc)
        return False


def resolve_runtime() -> RuntimeMode:
    """Resolve the effective runtime mode with fallback logic.

    If AGENTCORE_ENABLED=true but AgentCore is unreachable, falls back
    to LOCAL mode and logs a warning.

    Returns:
        The effective RuntimeMode to use.
    """
    mode = get_runtime_mode()

    if mode == RuntimeMode.AGENTCORE:
        if is_agentcore_available():
            logger.info("AgentCore is available. Running in managed mode.")
            return RuntimeMode.AGENTCORE
        else:
            logger.warning(
                "AgentCore is enabled but unreachable. "
                "Falling back to local Strands execution."
            )
            return RuntimeMode.LOCAL

    logger.info("Running in local mode (Strands SDK on ECS Fargate).")
    return RuntimeMode.LOCAL
