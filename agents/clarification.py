"""Clarification Agent module.

Implements the ClarificationAgent responsible for multi-turn requirements
gathering via smart question generation. Analyzes user descriptions, generates
clarifying questions for uncovered categories, and produces a complete
RequirementsProfile when sufficient information is gathered.

Responsibilities:
- Analyze system descriptions for already-stated requirements
- Generate clarifying questions with suggested defaults
- Detect skip-intent and apply defaults with documented assumptions
- Update RequirementsProfile incrementally across rounds
"""
