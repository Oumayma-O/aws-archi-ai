"""Unit test fixtures for AWS Architect AI agentic features.

Fixtures here provide isolated mocks for unit testing individual
agent components without external dependencies.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_bedrock_model():
    """A mocked Strands BedrockModel for agent unit tests."""
    model = MagicMock()
    model.invoke = AsyncMock(return_value=MagicMock(content="Mock response"))
    return model


@pytest.fixture
def mock_session_store():
    """A mocked SessionStore for testing agents without DynamoDB."""
    store = MagicMock()
    store.save = AsyncMock(return_value=None)
    store.load = AsyncMock(return_value=None)
    store.list_sessions = AsyncMock(return_value=[])
    return store
