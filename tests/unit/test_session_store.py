"""Unit tests for agents/session_store.py.

Uses moto to mock DynamoDB for isolated testing of SessionStore
CRUD operations, retry logic, and error handling.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import boto3
import pytest
from moto import mock_aws
from botocore.exceptions import ClientError
from unittest.mock import patch, MagicMock

from agents.session_store import SessionStore, SessionSummary
from agents.errors import SessionPersistenceError
from models.session import Session, WorkflowPhase, ConversationMessage


@pytest.fixture
def sample_session() -> Session:
    """A sample session for testing."""
    return Session(
        session_id="test-session-123",
        user_id="user-456",
        created_at=datetime(2024, 1, 15, 10, 0, 0),
        updated_at=datetime(2024, 1, 15, 11, 30, 0),
        current_phase=WorkflowPhase.CLARIFICATION,
        conversation_history=[
            ConversationMessage(
                role="user",
                content="I need a scalable e-commerce platform",
                timestamp=datetime(2024, 1, 15, 10, 0, 0),
                phase=WorkflowPhase.REQUIREMENTS_ANALYSIS,
            ),
            ConversationMessage(
                role="assistant",
                content="Let me ask some clarifying questions about your requirements.",
                timestamp=datetime(2024, 1, 15, 10, 0, 5),
                phase=WorkflowPhase.CLARIFICATION,
            ),
        ],
        clarification_rounds=1,
        is_complete=False,
    )


class TestSessionStoreSave:
    """Tests for SessionStore.save()."""

    @pytest.mark.asyncio
    async def test_save_persists_session(self, sample_session):
        """save() persists a session to DynamoDB."""
        with mock_aws():
            dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
            dynamodb.create_table(
                TableName="test-sessions",
                KeySchema=[{"AttributeName": "session_id", "KeyType": "HASH"}],
                AttributeDefinitions=[
                    {"AttributeName": "session_id", "AttributeType": "S"},
                    {"AttributeName": "user_id", "AttributeType": "S"},
                    {"AttributeName": "updated_at", "AttributeType": "S"},
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "user-sessions-index",
                        "KeySchema": [
                            {"AttributeName": "user_id", "KeyType": "HASH"},
                            {"AttributeName": "updated_at", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                    }
                ],
                BillingMode="PAY_PER_REQUEST",
            )

            store = SessionStore(table_name="test-sessions")
            store._dynamodb = dynamodb
            store._table = dynamodb.Table("test-sessions")

            await store.save(sample_session)

            # Verify it's in DynamoDB
            response = store._table.get_item(
                Key={"session_id": "test-session-123"}
            )
            item = response["Item"]
            assert item["session_id"] == "test-session-123"
            assert item["user_id"] == "user-456"
            assert item["current_phase"] == "clarification"
            assert "data" in item

    @pytest.mark.asyncio
    async def test_save_retries_on_failure(self, sample_session):
        """save() retries once before raising SessionPersistenceError."""
        store = SessionStore(table_name="test-sessions")
        mock_table = MagicMock()
        mock_table.put_item = MagicMock(
            side_effect=ClientError(
                {"Error": {"Code": "InternalServerError", "Message": "Transient"}},
                "PutItem",
            )
        )
        store._table = mock_table

        with pytest.raises(SessionPersistenceError) as exc_info:
            await store.save(sample_session)

        # Should have attempted twice
        assert mock_table.put_item.call_count == 2
        assert "after 2 attempts" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_save_succeeds_on_retry(self, sample_session):
        """save() succeeds if the second attempt works."""
        store = SessionStore(table_name="test-sessions")
        mock_table = MagicMock()
        # Fail first, succeed second
        mock_table.put_item = MagicMock(
            side_effect=[
                ClientError(
                    {"Error": {"Code": "InternalServerError", "Message": "Transient"}},
                    "PutItem",
                ),
                {"ResponseMetadata": {"HTTPStatusCode": 200}},
            ]
        )
        store._table = mock_table

        # Should not raise
        await store.save(sample_session)
        assert mock_table.put_item.call_count == 2


class TestSessionStoreLoad:
    """Tests for SessionStore.load()."""

    @pytest.mark.asyncio
    async def test_load_existing_session(self, sample_session):
        """load() returns a Session when the item exists."""
        with mock_aws():
            dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
            dynamodb.create_table(
                TableName="test-sessions",
                KeySchema=[{"AttributeName": "session_id", "KeyType": "HASH"}],
                AttributeDefinitions=[
                    {"AttributeName": "session_id", "AttributeType": "S"},
                    {"AttributeName": "user_id", "AttributeType": "S"},
                    {"AttributeName": "updated_at", "AttributeType": "S"},
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "user-sessions-index",
                        "KeySchema": [
                            {"AttributeName": "user_id", "KeyType": "HASH"},
                            {"AttributeName": "updated_at", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                    }
                ],
                BillingMode="PAY_PER_REQUEST",
            )

            store = SessionStore(table_name="test-sessions")
            store._dynamodb = dynamodb
            store._table = dynamodb.Table("test-sessions")

            # First save
            await store.save(sample_session)

            # Then load
            loaded = await store.load("test-session-123")
            assert loaded is not None
            assert loaded.session_id == "test-session-123"
            assert loaded.user_id == "user-456"
            assert loaded.current_phase == WorkflowPhase.CLARIFICATION
            assert len(loaded.conversation_history) == 2
            assert loaded.clarification_rounds == 1

    @pytest.mark.asyncio
    async def test_load_nonexistent_session_returns_none(self):
        """load() returns None when the session doesn't exist."""
        with mock_aws():
            dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
            dynamodb.create_table(
                TableName="test-sessions",
                KeySchema=[{"AttributeName": "session_id", "KeyType": "HASH"}],
                AttributeDefinitions=[
                    {"AttributeName": "session_id", "AttributeType": "S"},
                ],
                BillingMode="PAY_PER_REQUEST",
            )

            store = SessionStore(table_name="test-sessions")
            store._dynamodb = dynamodb
            store._table = dynamodb.Table("test-sessions")

            result = await store.load("nonexistent-id")
            assert result is None

    @pytest.mark.asyncio
    async def test_load_raises_on_client_error(self):
        """load() raises SessionPersistenceError on DynamoDB failure."""
        store = SessionStore(table_name="test-sessions")
        mock_table = MagicMock()
        mock_table.get_item = MagicMock(
            side_effect=ClientError(
                {"Error": {"Code": "ResourceNotFoundException", "Message": "Table not found"}},
                "GetItem",
            )
        )
        store._table = mock_table

        with pytest.raises(SessionPersistenceError) as exc_info:
            await store.load("some-id")

        assert "Failed to load session" in str(exc_info.value)


class TestSessionStoreListSessions:
    """Tests for SessionStore.list_sessions()."""

    @pytest.mark.asyncio
    async def test_list_sessions_returns_summaries(self):
        """list_sessions() returns SessionSummary objects ordered by recent first."""
        with mock_aws():
            dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
            dynamodb.create_table(
                TableName="test-sessions",
                KeySchema=[{"AttributeName": "session_id", "KeyType": "HASH"}],
                AttributeDefinitions=[
                    {"AttributeName": "session_id", "AttributeType": "S"},
                    {"AttributeName": "user_id", "AttributeType": "S"},
                    {"AttributeName": "updated_at", "AttributeType": "S"},
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "user-sessions-index",
                        "KeySchema": [
                            {"AttributeName": "user_id", "KeyType": "HASH"},
                            {"AttributeName": "updated_at", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                    }
                ],
                BillingMode="PAY_PER_REQUEST",
            )

            store = SessionStore(table_name="test-sessions")
            store._dynamodb = dynamodb
            store._table = dynamodb.Table("test-sessions")

            # Save two sessions for the same user
            session1 = Session(
                session_id="session-1",
                user_id="user-1",
                updated_at=datetime(2024, 1, 15, 10, 0, 0),
                current_phase=WorkflowPhase.CLARIFICATION,
                conversation_history=[
                    ConversationMessage(
                        role="user",
                        content="Build me an e-commerce platform",
                        timestamp=datetime(2024, 1, 15, 10, 0, 0),
                    ),
                ],
            )
            session2 = Session(
                session_id="session-2",
                user_id="user-1",
                updated_at=datetime(2024, 1, 16, 12, 0, 0),
                current_phase=WorkflowPhase.DESIGN,
                conversation_history=[
                    ConversationMessage(
                        role="user",
                        content="Design a serverless API",
                        timestamp=datetime(2024, 1, 16, 12, 0, 0),
                    ),
                ],
            )

            await store.save(session1)
            await store.save(session2)

            # List sessions for user-1
            summaries = await store.list_sessions("user-1")
            assert len(summaries) == 2
            # Most recent first (descending order)
            assert summaries[0].session_id == "session-2"
            assert summaries[0].current_phase == WorkflowPhase.DESIGN
            assert summaries[0].title == "Design a serverless API"
            assert summaries[1].session_id == "session-1"
            assert summaries[1].current_phase == WorkflowPhase.CLARIFICATION

    @pytest.mark.asyncio
    async def test_list_sessions_empty_for_unknown_user(self):
        """list_sessions() returns empty list for unknown user."""
        with mock_aws():
            dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
            dynamodb.create_table(
                TableName="test-sessions",
                KeySchema=[{"AttributeName": "session_id", "KeyType": "HASH"}],
                AttributeDefinitions=[
                    {"AttributeName": "session_id", "AttributeType": "S"},
                    {"AttributeName": "user_id", "AttributeType": "S"},
                    {"AttributeName": "updated_at", "AttributeType": "S"},
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "user-sessions-index",
                        "KeySchema": [
                            {"AttributeName": "user_id", "KeyType": "HASH"},
                            {"AttributeName": "updated_at", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                    }
                ],
                BillingMode="PAY_PER_REQUEST",
            )

            store = SessionStore(table_name="test-sessions")
            store._dynamodb = dynamodb
            store._table = dynamodb.Table("test-sessions")

            summaries = await store.list_sessions("unknown-user")
            assert summaries == []

    @pytest.mark.asyncio
    async def test_list_sessions_raises_on_client_error(self):
        """list_sessions() raises SessionPersistenceError on DynamoDB failure."""
        store = SessionStore(table_name="test-sessions")
        mock_table = MagicMock()
        mock_table.query = MagicMock(
            side_effect=ClientError(
                {"Error": {"Code": "ResourceNotFoundException", "Message": "Table not found"}},
                "Query",
            )
        )
        store._table = mock_table

        with pytest.raises(SessionPersistenceError) as exc_info:
            await store.list_sessions("user-1")

        assert "Failed to list sessions" in str(exc_info.value)


class TestSessionStoreEnvironment:
    """Tests for environment variable configuration."""

    def test_default_table_name(self):
        """SessionStore uses 'architect-sessions' as default table name."""
        with patch.dict("os.environ", {}, clear=True):
            # Remove SESSION_TABLE_NAME if it exists
            import os
            os.environ.pop("SESSION_TABLE_NAME", None)
            store = SessionStore()
            assert store._table_name == "architect-sessions"

    def test_env_var_table_name(self):
        """SessionStore reads table name from SESSION_TABLE_NAME env var."""
        with patch.dict("os.environ", {"SESSION_TABLE_NAME": "custom-table"}):
            store = SessionStore()
            assert store._table_name == "custom-table"

    def test_explicit_table_name_overrides_env(self):
        """Explicit table_name parameter overrides environment variable."""
        with patch.dict("os.environ", {"SESSION_TABLE_NAME": "from-env"}):
            store = SessionStore(table_name="explicit-table")
            assert store._table_name == "explicit-table"
