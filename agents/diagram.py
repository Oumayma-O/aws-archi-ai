"""Diagram Agent module.

Implements the DiagramAgent that generates professional AWS architecture diagrams
via the Draw.io MCP server or falls back to local XML rendering.

Responsibilities:
- Generate Draw.io XML with AWS icon stencils, VPC boundaries, AZ layouts
- Fall back to local XML generation when MCP unavailable
- Generate PNG rendering for inline display
- Ensure diagram nodes correspond to architecture services
"""
