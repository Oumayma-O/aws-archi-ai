"""Research Agent module.

Implements the ResearchAgent that queries MCP servers for AWS documentation,
reference architectures, Well-Architected Framework guidance, and pricing data.

Responsibilities:
- Query AWS Docs MCP for reference architectures and best practices
- Query Pricing MCP for service pricing in user's region
- Produce cost comparisons for alternative services
- Handle MCP unavailability with graceful degradation
- Calculate monthly costs from profile traffic patterns
"""
