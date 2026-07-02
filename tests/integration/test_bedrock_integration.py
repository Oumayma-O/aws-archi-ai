"""Integration tests for Bedrock client request structure with mocked boto3."""

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from models.architecture import ArchitectureModel


class TestBedrockInvokeModelRequestStructure:
    """Test that invoke_model sends the correct request structure to Bedrock."""

    def _mock_bedrock_response(self, response_text: str) -> MagicMock:
        """Create a mocked Bedrock response with the given text."""
        body_content = json.dumps(
            {
                "content": [{"type": "text", "text": response_text}],
                "stop_reason": "end_turn",
            }
        ).encode("utf-8")
        mock_body = BytesIO(body_content)
        return {"body": mock_body}

    @patch("services.bedrock.load_config")
    @patch("services.bedrock.get_bedrock_client")
    def test_invoke_model_sends_correct_model_id(
        self, mock_get_client, mock_load_config
    ):
        """invoke_model passes the correct modelId to the Bedrock client."""
        from services.bedrock import invoke_model

        mock_config = MagicMock()
        mock_config.aws_region = "us-east-1"
        mock_config.aws_profile = None
        mock_load_config.return_value = mock_config

        mock_client = MagicMock()
        mock_client.invoke_model.return_value = self._mock_bedrock_response(
            "Hello world"
        )
        mock_get_client.return_value = mock_client

        invoke_model(
            prompt="Test prompt",
            model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
            temperature=0.7,
        )

        call_kwargs = mock_client.invoke_model.call_args[1]
        assert call_kwargs["modelId"] == "us.anthropic.claude-sonnet-4-20250514-v1:0"

    @patch("services.bedrock.load_config")
    @patch("services.bedrock.get_bedrock_client")
    def test_invoke_model_sends_correct_body_structure(
        self, mock_get_client, mock_load_config
    ):
        """invoke_model sends the correct body structure with anthropic_version, max_tokens, temperature, and messages."""
        from services.bedrock import invoke_model

        mock_config = MagicMock()
        mock_config.aws_region = "us-east-1"
        mock_config.aws_profile = None
        mock_load_config.return_value = mock_config

        mock_client = MagicMock()
        mock_client.invoke_model.return_value = self._mock_bedrock_response(
            "Response text"
        )
        mock_get_client.return_value = mock_client

        invoke_model(
            prompt="Describe a serverless API",
            model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
            temperature=0.5,
        )

        call_kwargs = mock_client.invoke_model.call_args[1]
        body = json.loads(call_kwargs["body"])

        assert body["anthropic_version"] == "bedrock-2023-05-31"
        assert body["max_tokens"] == 4096
        assert body["temperature"] == 0.5
        assert body["messages"] == [
            {"role": "user", "content": "Describe a serverless API"}
        ]

    @patch("services.bedrock.load_config")
    @patch("services.bedrock.get_bedrock_client")
    def test_invoke_model_sends_correct_content_type_and_accept(
        self, mock_get_client, mock_load_config
    ):
        """invoke_model sends contentType and accept as application/json."""
        from services.bedrock import invoke_model

        mock_config = MagicMock()
        mock_config.aws_region = "us-east-1"
        mock_config.aws_profile = None
        mock_load_config.return_value = mock_config

        mock_client = MagicMock()
        mock_client.invoke_model.return_value = self._mock_bedrock_response(
            "Some response"
        )
        mock_get_client.return_value = mock_client

        invoke_model(
            prompt="Test prompt",
            model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
            temperature=1.0,
        )

        call_kwargs = mock_client.invoke_model.call_args[1]
        assert call_kwargs["contentType"] == "application/json"
        assert call_kwargs["accept"] == "application/json"

    @patch("services.bedrock.load_config")
    @patch("services.bedrock.get_bedrock_client")
    def test_invoke_model_returns_response_text(
        self, mock_get_client, mock_load_config
    ):
        """invoke_model returns the text content from the Bedrock response."""
        from services.bedrock import invoke_model

        mock_config = MagicMock()
        mock_config.aws_region = "us-east-1"
        mock_config.aws_profile = None
        mock_load_config.return_value = mock_config

        expected_text = '{"title": "Test Architecture"}'
        mock_client = MagicMock()
        mock_client.invoke_model.return_value = self._mock_bedrock_response(
            expected_text
        )
        mock_get_client.return_value = mock_client

        result = invoke_model(
            prompt="Test prompt",
            model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
            temperature=0.7,
        )

        assert result == expected_text

    @patch("services.bedrock.load_config")
    @patch("services.bedrock.get_bedrock_client")
    def test_invoke_model_temperature_zero(
        self, mock_get_client, mock_load_config
    ):
        """invoke_model correctly passes temperature=0.0."""
        from services.bedrock import invoke_model

        mock_config = MagicMock()
        mock_config.aws_region = "us-east-1"
        mock_config.aws_profile = None
        mock_load_config.return_value = mock_config

        mock_client = MagicMock()
        mock_client.invoke_model.return_value = self._mock_bedrock_response("ok")
        mock_get_client.return_value = mock_client

        invoke_model(prompt="Test", model_id="test-model", temperature=0.0)
        call_kwargs = mock_client.invoke_model.call_args[1]
        body = json.loads(call_kwargs["body"])
        assert body["temperature"] == 0.0

    @patch("services.bedrock.load_config")
    @patch("services.bedrock.get_bedrock_client")
    def test_invoke_model_temperature_one(
        self, mock_get_client, mock_load_config
    ):
        """invoke_model correctly passes temperature=1.0."""
        from services.bedrock import invoke_model

        mock_config = MagicMock()
        mock_config.aws_region = "us-east-1"
        mock_config.aws_profile = None
        mock_load_config.return_value = mock_config

        mock_client = MagicMock()
        mock_client.invoke_model.return_value = self._mock_bedrock_response("ok")
        mock_get_client.return_value = mock_client

        invoke_model(prompt="Test", model_id="test-model", temperature=1.0)
        call_kwargs = mock_client.invoke_model.call_args[1]
        body = json.loads(call_kwargs["body"])
        assert body["temperature"] == 1.0
