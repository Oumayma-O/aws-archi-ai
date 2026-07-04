"""Unit tests for agents/mcp_config.py MCP client factory functions."""

import os
from unittest.mock import patch

import pytest

from agents.mcp_config import (
    create_docs_mcp,
    create_drawio_mcp,
    create_pricing_mcp,
    _DEFAULT_DOCS_COMMAND,
    _DEFAULT_PRICING_COMMAND,
    _DEFAULT_DRAWIO_COMMAND,
)


@pytest.fixture(autouse=True)
def _clear_mcp_env(monkeypatch):
    """Isolate tests from the developer's real .env.

    load_dotenv() (triggered by other imports) can put real MCP_*_URL /
    MCP_*_COMMAND values in the process env, which silently flips these
    factories onto the HTTP path and defeats the stdio mocks.
    """
    for var in (
        "MCP_DOCS_URL", "MCP_AWS_DOCS_COMMAND",
        "MCP_PRICING_URL", "MCP_PRICING_COMMAND",
        "MCP_DRAWIO_URL", "MCP_DRAWIO_COMMAND",
    ):
        monkeypatch.delenv(var, raising=False)


class TestCreateDocsMcp:
    """Tests for create_docs_mcp factory function."""

    def test_returns_mcp_client_with_default_command(self):
        """Should return an MCPClient using the default stdio command."""
        from strands.tools.mcp import MCPClient

        client = create_docs_mcp()
        assert client is not None
        assert isinstance(client, MCPClient)

    def test_uses_custom_command_from_env(self):
        """Should use MCP_AWS_DOCS_COMMAND env var when set."""
        from strands.tools.mcp import MCPClient

        with patch.dict(os.environ, {"MCP_AWS_DOCS_COMMAND": "node custom-server.js"}):
            client = create_docs_mcp()
            assert client is not None
            assert isinstance(client, MCPClient)

    def test_prefers_url_over_command(self):
        """Should use HTTP transport when MCP_DOCS_URL is set."""
        from strands.tools.mcp import MCPClient

        with patch.dict(os.environ, {
            "MCP_DOCS_URL": "http://localhost/mcp",
            "MCP_AWS_DOCS_COMMAND": "node other-server.js",
        }):
            client = create_docs_mcp()
            assert client is not None
            assert isinstance(client, MCPClient)

    def test_returns_none_on_import_error(self):
        """Should return None and log warning when dependencies are missing."""
        with patch("agents.mcp_config._create_mcp_client_stdio", side_effect=ImportError("no mcp")):
            client = create_docs_mcp()
            assert client is None

    def test_returns_none_on_general_exception(self):
        """Should return None and log warning on unexpected errors."""
        with patch("agents.mcp_config._create_mcp_client_stdio", side_effect=RuntimeError("oops")):
            client = create_docs_mcp()
            assert client is None


class TestCreatePricingMcp:
    """Tests for create_pricing_mcp factory function."""

    def test_returns_mcp_client_with_default_command(self):
        """Should return an MCPClient using the default stdio command."""
        from strands.tools.mcp import MCPClient

        client = create_pricing_mcp()
        assert client is not None
        assert isinstance(client, MCPClient)

    def test_uses_custom_command_from_env(self):
        """Should use MCP_PRICING_COMMAND env var when set."""
        from strands.tools.mcp import MCPClient

        with patch.dict(os.environ, {"MCP_PRICING_COMMAND": "python pricing_server.py"}):
            client = create_pricing_mcp()
            assert client is not None
            assert isinstance(client, MCPClient)

    def test_prefers_url_over_command(self):
        """Should use HTTP transport when MCP_PRICING_URL is set."""
        from strands.tools.mcp import MCPClient

        with patch.dict(os.environ, {"MCP_PRICING_URL": "https://pricing.example.com/mcp"}):
            client = create_pricing_mcp()
            assert client is not None
            assert isinstance(client, MCPClient)

    def test_returns_none_on_import_error(self):
        """Should return None when dependencies are missing."""
        with patch("agents.mcp_config._create_mcp_client_http", side_effect=ImportError("no dep")):
            with patch.dict(os.environ, {"MCP_PRICING_URL": "http://localhost/mcp"}):
                client = create_pricing_mcp()
                assert client is None

    def test_returns_none_on_general_exception(self):
        """Should return None on unexpected errors."""
        with patch("agents.mcp_config._create_mcp_client_stdio", side_effect=OSError("failed")):
            client = create_pricing_mcp()
            assert client is None


class TestCreateDrawioMcp:
    """Tests for create_drawio_mcp factory function."""

    def test_returns_mcp_client_with_default_command(self):
        """Should return an MCPClient using the default stdio command."""
        from strands.tools.mcp import MCPClient

        client = create_drawio_mcp()
        assert client is not None
        assert isinstance(client, MCPClient)

    def test_uses_custom_command_from_env(self):
        """Should use MCP_DRAWIO_COMMAND env var when set."""
        from strands.tools.mcp import MCPClient

        with patch.dict(os.environ, {"MCP_DRAWIO_COMMAND": "drawio-mcp serve"}):
            client = create_drawio_mcp()
            assert client is not None
            assert isinstance(client, MCPClient)

    def test_prefers_url_over_command(self):
        """Should use HTTP transport when MCP_DRAWIO_URL is set."""
        from strands.tools.mcp import MCPClient

        with patch.dict(os.environ, {"MCP_DRAWIO_URL": "http://localhost/drawio"}):
            client = create_drawio_mcp()
            assert client is not None
            assert isinstance(client, MCPClient)

    def test_returns_none_on_import_error(self):
        """Should return None when dependencies are missing."""
        with patch("agents.mcp_config._create_mcp_client_stdio", side_effect=ImportError("missing")):
            client = create_drawio_mcp()
            assert client is None

    def test_returns_none_on_general_exception(self):
        """Should return None on unexpected errors."""
        with patch("agents.mcp_config._create_mcp_client_http", side_effect=ConnectionError("refused")):
            with patch.dict(os.environ, {"MCP_DRAWIO_URL": "http://bad-host/mcp"}):
                client = create_drawio_mcp()
                assert client is None


class TestDefaultCommands:
    """Tests for default command constants."""

    def test_default_docs_command(self):
        assert _DEFAULT_DOCS_COMMAND == "uvx awslabs.aws-documentation-mcp-server@latest"

    def test_default_pricing_command(self):
        assert _DEFAULT_PRICING_COMMAND == "uvx awslabs.aws-pricing-mcp-server@latest"

    def test_default_drawio_command(self):
        assert _DEFAULT_DRAWIO_COMMAND == "npx -y @drawio/mcp"
