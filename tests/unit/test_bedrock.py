"""Unit tests for services/bedrock.py.

Tests client caching, exception mapping, logging, and timeout handling.
"""

import json
import logging
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import (
    ClientError,
    ConnectionError as BotocoreConnectionError,
    EndpointConnectionError,
    ReadTimeoutError,
)

from services.bedrock import get_bedrock_client, invoke_model
from services.exceptions import (
    BedrockConnectionError,
    BedrockThrottlingError,
    BedrockTimeoutError,
)


@pytest.fixture(autouse=True)
def clear_client_cache():
    """Clear the lru_cache before each test to ensure isolation."""
    get_bedrock_client.cache_clear()
    yield
    get_bedrock_client.cache_clear()


@pytest.fixture
def mock_config():
    """Mock the load_config function to return test configuration."""
    with patch("services.bedrock.load_config") as mock:
        mock.return_value = MagicMock(
            aws_region="us-east-1",
            aws_profile=None,
        )
        yield mock


@pytest.fixture
def mock_boto_session():
    """Mock boto3.Session to return a mock client."""
    with patch("services.bedrock.boto3.Session") as mock_session_cls:
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session.client.return_value = mock_client
        mock_session_cls.return_value = mock_session
        yield mock_client


class TestGetBedrockClient:
    """Tests for get_bedrock_client function."""

    def test_creates_client_with_region(self, mock_boto_session):
        """Client is created with the specified region."""
        with patch("services.bedrock.boto3.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_client = MagicMock()
            mock_session.client.return_value = mock_client
            mock_session_cls.return_value = mock_session

            result = get_bedrock_client(region="us-west-2")

            mock_session_cls.assert_called_once_with(region_name="us-west-2")
            assert result == mock_client

    def test_creates_client_with_profile(self):
        """Client is created with profile when specified."""
        with patch("services.bedrock.boto3.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_client = MagicMock()
            mock_session.client.return_value = mock_client
            mock_session_cls.return_value = mock_session

            get_bedrock_client(region="us-east-1", profile="dev")

            mock_session_cls.assert_called_once_with(
                region_name="us-east-1", profile_name="dev"
            )

    def test_caches_client_instance(self):
        """Same client instance is returned for same arguments."""
        with patch("services.bedrock.boto3.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_client = MagicMock()
            mock_session.client.return_value = mock_client
            mock_session_cls.return_value = mock_session

            client1 = get_bedrock_client(region="us-east-1")
            client2 = get_bedrock_client(region="us-east-1")

            assert client1 is client2
            # Session should only be created once
            assert mock_session_cls.call_count == 1


class TestInvokeModel:
    """Tests for invoke_model function."""

    def _make_response(self, text: str) -> dict:
        """Create a mock Bedrock response body."""
        body_content = json.dumps(
            {
                "content": [{"type": "text", "text": text}],
                "stop_reason": "end_turn",
            }
        ).encode()
        body = MagicMock()
        body.read.return_value = body_content
        return {"body": body}

    def test_successful_invocation(self, mock_config):
        """invoke_model returns response text on success."""
        with patch("services.bedrock.get_bedrock_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.invoke_model.return_value = self._make_response(
                '{"title": "test"}'
            )
            mock_get_client.return_value = mock_client

            result = invoke_model(
                prompt="Design a web app",
                model_id="anthropic.claude-3-sonnet",
                temperature=0.7,
            )

            assert result == '{"title": "test"}'

    def test_logs_request_info(self, mock_config, caplog):
        """invoke_model logs model_id and request size at INFO level."""
        with patch("services.bedrock.get_bedrock_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.invoke_model.return_value = self._make_response("ok")
            mock_get_client.return_value = mock_client

            with caplog.at_level(logging.INFO, logger="services.bedrock"):
                invoke_model(
                    prompt="Hello world",
                    model_id="anthropic.claude-3-sonnet",
                    temperature=0.5,
                )

            assert any(
                "anthropic.claude-3-sonnet" in record.message
                and "11" in record.message  # len("Hello world") == 11
                for record in caplog.records
            )

    def test_maps_read_timeout_to_bedrock_timeout_error(self, mock_config):
        """ReadTimeoutError is mapped to BedrockTimeoutError."""
        with patch("services.bedrock.get_bedrock_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.invoke_model.side_effect = ReadTimeoutError(
                endpoint_url="https://bedrock.us-east-1.amazonaws.com"
            )
            mock_get_client.return_value = mock_client

            with pytest.raises(BedrockTimeoutError, match="timed out"):
                invoke_model(
                    prompt="test",
                    model_id="anthropic.claude-3-sonnet",
                    temperature=0.5,
                )

    def test_maps_endpoint_connection_error(self, mock_config):
        """EndpointConnectionError is mapped to BedrockConnectionError."""
        with patch("services.bedrock.get_bedrock_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.invoke_model.side_effect = EndpointConnectionError(
                endpoint_url="https://bedrock.us-east-1.amazonaws.com"
            )
            mock_get_client.return_value = mock_client

            with pytest.raises(BedrockConnectionError, match="connect"):
                invoke_model(
                    prompt="test",
                    model_id="anthropic.claude-3-sonnet",
                    temperature=0.5,
                )

    def test_maps_connection_error(self, mock_config):
        """botocore ConnectionError is mapped to BedrockConnectionError."""
        with patch("services.bedrock.get_bedrock_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.invoke_model.side_effect = BotocoreConnectionError(
                error="Network unreachable"
            )
            mock_get_client.return_value = mock_client

            with pytest.raises(BedrockConnectionError, match="Connection error"):
                invoke_model(
                    prompt="test",
                    model_id="anthropic.claude-3-sonnet",
                    temperature=0.5,
                )

    def test_maps_throttling_client_error(self, mock_config):
        """ClientError with ThrottlingException code maps to BedrockThrottlingError."""
        with patch("services.bedrock.get_bedrock_client") as mock_get_client:
            mock_client = MagicMock()
            error_response = {
                "Error": {
                    "Code": "ThrottlingException",
                    "Message": "Rate exceeded",
                }
            }
            mock_client.invoke_model.side_effect = ClientError(
                error_response=error_response,
                operation_name="InvokeModel",
            )
            mock_get_client.return_value = mock_client

            with pytest.raises(BedrockThrottlingError, match="throttled"):
                invoke_model(
                    prompt="test",
                    model_id="anthropic.claude-3-sonnet",
                    temperature=0.5,
                )

    def test_maps_other_client_error_to_connection_error(self, mock_config):
        """ClientError with non-throttling code maps to BedrockConnectionError."""
        with patch("services.bedrock.get_bedrock_client") as mock_get_client:
            mock_client = MagicMock()
            error_response = {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": "Access denied",
                }
            }
            mock_client.invoke_model.side_effect = ClientError(
                error_response=error_response,
                operation_name="InvokeModel",
            )
            mock_get_client.return_value = mock_client

            with pytest.raises(BedrockConnectionError, match="AccessDeniedException"):
                invoke_model(
                    prompt="test",
                    model_id="anthropic.claude-3-sonnet",
                    temperature=0.5,
                )

    def test_sends_correct_request_body(self, mock_config):
        """invoke_model sends properly structured request body."""
        with patch("services.bedrock.get_bedrock_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.invoke_model.return_value = self._make_response("response")
            mock_get_client.return_value = mock_client

            invoke_model(
                prompt="Describe an architecture",
                model_id="anthropic.claude-3-sonnet",
                temperature=0.8,
            )

            call_kwargs = mock_client.invoke_model.call_args.kwargs
            assert call_kwargs["modelId"] == "anthropic.claude-3-sonnet"
            assert call_kwargs["contentType"] == "application/json"
            assert call_kwargs["accept"] == "application/json"

            body = json.loads(call_kwargs["body"])
            assert body["temperature"] == 0.8
            assert body["messages"][0]["content"] == "Describe an architecture"
            assert body["anthropic_version"] == "bedrock-2023-05-31"
