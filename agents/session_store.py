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

from __future__ import annotations

import logging
import os
from datetime import datetime

import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field

from agents.errors import SessionPersistenceError
from models.session import Session, WorkflowPhase

logger = logging.getLogger(__name__)


class SessionSummary(BaseModel):
    """Lightweight summary of a session for listing purposes."""

    session_id: str
    title: str = Field(default="Untitled Session")
    updated_at: datetime
    current_phase: WorkflowPhase


class SessionStore:
    """DynamoDB-backed session persistence."""

    def __init__(self, table_name: str | None = None):
        """Initialize the session store.

        Args:
            table_name: DynamoDB table name. Defaults to the
                SESSION_TABLE_NAME environment variable or "architect-sessions".
        """
        self._table_name = (
            table_name
            or os.environ.get("SESSION_TABLE_NAME", "architect-sessions")
        )
        region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "eu-west-1"))
        self._dynamodb = boto3.resource("dynamodb", region_name=region)
        self._table = self._dynamodb.Table(self._table_name)

    async def save(self, session: Session) -> None:
        """Persist session state to DynamoDB.

        Serializes the full Session model as JSON and stores it as a single
        ``data`` attribute alongside indexing attributes. Retries once on
        failure before raising SessionPersistenceError.

        Args:
            session: The session to persist.

        Raises:
            SessionPersistenceError: If persisting fails after one retry.
        """
        item = {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "updated_at": session.updated_at.isoformat(),
            "current_phase": session.current_phase.value,
            "data": session.model_dump_json(),
        }

        last_error: Exception | None = None
        for attempt in range(2):
            try:
                self._table.put_item(Item=item)
                return
            except ClientError as exc:
                last_error = exc
                logger.warning(
                    "DynamoDB put_item failed (attempt %d/2) for session %s: %s",
                    attempt + 1,
                    session.session_id,
                    exc,
                )

        raise SessionPersistenceError(
            f"Failed to save session {session.session_id} after 2 attempts: {last_error}"
        )

    async def load(self, session_id: str) -> Session | None:
        """Load a session by ID. Returns None if not found.

        Args:
            session_id: The unique session identifier.

        Returns:
            Session if found, None otherwise.

        Raises:
            SessionPersistenceError: If the DynamoDB read fails.
        """
        try:
            response = self._table.get_item(Key={"session_id": session_id})
        except ClientError as exc:
            raise SessionPersistenceError(
                f"Failed to load session {session_id}: {exc}"
            ) from exc

        item = response.get("Item")
        if item is None:
            return None

        data = item.get("data")
        if data is None:
            return None

        return Session.model_validate_json(data)

    async def list_sessions(self, user_id: str) -> list[SessionSummary]:
        """List active sessions for a user ordered by last activity (most recent first).

        Queries the ``user-sessions-index`` GSI with partition key ``user_id``
        and sort key ``updated_at`` in descending order.

        Args:
            user_id: The user identifier.

        Returns:
            List of session summaries ordered by last activity.

        Raises:
            SessionPersistenceError: If the DynamoDB query fails.
        """
        try:
            response = self._table.query(
                IndexName="user-sessions-index",
                KeyConditionExpression="user_id = :uid",
                ExpressionAttributeValues={":uid": user_id},
                ScanIndexForward=False,  # Descending order (most recent first)
            )
        except ClientError as exc:
            raise SessionPersistenceError(
                f"Failed to list sessions for user {user_id}: {exc}"
            ) from exc

        summaries: list[SessionSummary] = []
        for item in response.get("Items", []):
            # Derive a title from the session data if available
            title = _extract_title(item)
            summaries.append(
                SessionSummary(
                    session_id=item["session_id"],
                    title=title,
                    updated_at=datetime.fromisoformat(item["updated_at"]),
                    current_phase=WorkflowPhase(item["current_phase"]),
                )
            )

        return summaries


def _extract_title(item: dict) -> str:
    """Extract a human-readable title from a session DynamoDB item.

    Attempts to derive the title from the session data (first user message),
    falling back to a generic label.
    """
    data = item.get("data")
    if data is None:
        return "Untitled Session"

    try:
        session = Session.model_validate_json(data)
        # Use the first user message content as a title (truncated)
        for msg in session.conversation_history:
            if msg.role == "user":
                content = msg.content.strip()
                if len(content) > 60:
                    return content[:57] + "..."
                return content
    except Exception:
        pass

    return "Untitled Session"
