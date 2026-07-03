"""MCP Configuration module.

Provides factory functions for creating MCP (Model Context Protocol) client
instances used by the Research and Diagram agents.

Responsibilities:
- Create and configure AWS Docs MCP client
- Create and configure AWS Pricing MCP client
- Create and configure Draw.io MCP client
- Load server URLs/commands from environment variables
- Handle connection failures gracefully
"""
