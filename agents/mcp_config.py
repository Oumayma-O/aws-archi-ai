"""MCP Configuration module.

Provides factory functions for creating MCP (Model Context Protocol) client
instances used by the Research and Diagram agents.

Responsibilities:
- Create and configure AWS Docs MCP client
- Create and configure AWS Pricing MCP client
- Create and configure Draw.io MCP client
- Load server URLs/commands from environment variables
- Handle connection failures gracefully

Environment Variables:
- MCP_AWS_DOCS_COMMAND: Command to start the AWS Docs MCP server
    (default: "npx @anthropic/mcp-server-aws-docs")
- MCP_PRICING_COMMAND: Command for the pricing server
    (default: "npx @anthropic/mcp-server-aws-pricing")
- MCP_DRAWIO_COMMAND: Command for the Draw.io server
    (default: "npx @anthropic/mcp-server-drawio")
- MCP_DOCS_URL: Alternative HTTP URL for docs MCP (if running as HTTP server)
- MCP_PRICING_URL: Alternative HTTP URL for pricing MCP
- MCP_DRAWIO_URL: Alternative HTTP URL for Draw.io MCP
"""

from __future__ import annotations

import logging
import os
import shlex
from functools import partial
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from strands.tools.mcp import MCPClient

logger = logging.getLogger(__name__)

# Default commands for MCP servers (used when no URL or custom command is set)
_DEFAULT_DOCS_COMMAND = "npx @anthropic/mcp-server-aws-docs"
_DEFAULT_PRICING_COMMAND = "npx @anthropic/mcp-server-aws-pricing"
_DEFAULT_DRAWIO_COMMAND = "npx @anthropic/mcp-server-drawio"


def _create_mcp_client_stdio(command: str) -> "MCPClient":
    """Create an MCPClient using StdioTransport from a shell command string.

    Args:
        command: A shell command string to start the MCP server process.

    Returns:
        A configured MCPClient instance using stdio transport.
    """
    from mcp import StdioServerParameters, stdio_client
    from strands.tools.mcp import MCPClient

    parts = shlex.split(command)
    server_params = StdioServerParameters(command=parts[0], args=parts[1:])
    transport_callable = partial(stdio_client, server=server_params)
    return MCPClient(transport_callable)


def _create_mcp_client_http(url: str) -> "MCPClient":
    """Create an MCPClient using StreamableHTTPTransport from a URL.

    Args:
        url: The HTTP(S) URL of the running MCP server.

    Returns:
        A configured MCPClient instance using HTTP transport.
    """
    from mcp.client.streamable_http import streamablehttp_client
    from strands.tools.mcp import MCPClient

    transport_callable = partial(streamablehttp_client, url=url)
    return MCPClient(transport_callable)


def create_docs_mcp() -> "MCPClient | None":
    """Create AWS Documentation MCP client.

    Checks for ``MCP_DOCS_URL`` first (HTTP transport). If not set, falls back
    to ``MCP_AWS_DOCS_COMMAND`` (stdio transport) or the default command.

    Returns:
        Configured MCPClient for AWS documentation queries, or None if
        creation fails due to missing dependencies.
    """
    try:
        url = os.environ.get("MCP_DOCS_URL")
        if url:
            logger.info("Creating AWS Docs MCP client with HTTP transport: %s", url)
            return _create_mcp_client_http(url)

        command = os.environ.get("MCP_AWS_DOCS_COMMAND", _DEFAULT_DOCS_COMMAND)
        logger.info("Creating AWS Docs MCP client with stdio transport: %s", command)
        return _create_mcp_client_stdio(command)
    except ImportError as exc:
        logger.warning(
            "Failed to create AWS Docs MCP client — missing dependency: %s", exc
        )
        return None
    except Exception as exc:
        logger.warning(
            "Failed to create AWS Docs MCP client: %s", exc
        )
        return None


def create_pricing_mcp() -> "MCPClient | None":
    """Create AWS Pricing MCP client.

    Checks for ``MCP_PRICING_URL`` first (HTTP transport). If not set, falls
    back to ``MCP_PRICING_COMMAND`` (stdio transport) or the default command.

    Returns:
        Configured MCPClient for pricing data queries, or None if
        creation fails due to missing dependencies.
    """
    try:
        url = os.environ.get("MCP_PRICING_URL")
        if url:
            logger.info("Creating Pricing MCP client with HTTP transport: %s", url)
            return _create_mcp_client_http(url)

        command = os.environ.get("MCP_PRICING_COMMAND", _DEFAULT_PRICING_COMMAND)
        logger.info("Creating Pricing MCP client with stdio transport: %s", command)
        return _create_mcp_client_stdio(command)
    except ImportError as exc:
        logger.warning(
            "Failed to create Pricing MCP client — missing dependency: %s", exc
        )
        return None
    except Exception as exc:
        logger.warning(
            "Failed to create Pricing MCP client: %s", exc
        )
        return None


def create_drawio_mcp() -> "MCPClient | None":
    """Create Draw.io MCP client.

    Checks for ``MCP_DRAWIO_URL`` first (HTTP transport). If not set, falls
    back to ``MCP_DRAWIO_COMMAND`` (stdio transport) or the default command.

    Returns:
        Configured MCPClient for diagram generation, or None if
        creation fails due to missing dependencies.
    """
    try:
        url = os.environ.get("MCP_DRAWIO_URL")
        if url:
            logger.info("Creating Draw.io MCP client with HTTP transport: %s", url)
            return _create_mcp_client_http(url)

        command = os.environ.get("MCP_DRAWIO_COMMAND", _DEFAULT_DRAWIO_COMMAND)
        logger.info("Creating Draw.io MCP client with stdio transport: %s", command)
        return _create_mcp_client_stdio(command)
    except ImportError as exc:
        logger.warning(
            "Failed to create Draw.io MCP client — missing dependency: %s", exc
        )
        return None
    except Exception as exc:
        logger.warning(
            "Failed to create Draw.io MCP client: %s", exc
        )
        return None
