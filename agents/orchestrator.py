"""Orchestrator Agent module.

Implements the top-level OrchestratorAgent that manages workflow phases and
delegates to specialized sub-agents (Clarification, Research, Design, Diagram)
using the Strands agents-as-tools pattern.

Responsibilities:
- Manage workflow phase transitions in strict order
- Pass accumulated context between phases
- Implement retry and degradation strategy
- Handle session persistence via SessionStore
- Enforce max 5 clarification rounds
- Stream AgentEvents to the UI layer
"""
