"""Session Store module.

Implements DynamoDB-backed session persistence for the agentic workflow.
Sessions survive container restarts and support resume-after-inactivity.

Responsibilities:
- Save session state to DynamoDB after each phase transition
- Load existing sessions by ID for workflow resumption
- List active sessions for a user ordered by last activity
- Handle serialization of Pydantic models to/from DynamoDB items
- Implement retry logic for persistence failures
"""
