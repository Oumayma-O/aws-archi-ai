"""Integration tests for Bedrock client request structure with mocked boto3.

Tests verify that invoke_model sends correct parameters to the Converse API.
"""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestBedrockInvokeModelRequestStructure:
    """Test that invoke_model sends the correct request structure to Bedrock Converse API."""

    def _make_converse_response(self, response_text: str) -> dict:
        """Create a mocked Converse API response."""
        return {
            "output": {
                "message": {
                    "content": [{"text": response_text}]
                }
            }
        }

    @patch("services.bedrock.load_config")
    @patch("services.bedrock.get_bedrock_client")
    def test_invoke_model_sends_correct_model_id(
        self, mock_get_client, mock_load_config
    ):
        """invoke_model passes the correct modelId to client.converse()."""
        from services.bedrock import invoke_model

        mock_config = MagicMock()
        mock_config.aws_region = "eu-west-1"
        mock_config.aws_profile = None
        mock_load_config.return_value = mock_config

        mock_client = MagicMock()
        mock_client.converse.return_value = self._make_converse_response("hello")
        mock_get_client.return_value = mock_client

        invoke_model(
            prompt="Test prompt",
            model_id="eu.anthropic.claude-haiku-4-5-20251001-v1:0",
            temperature=0.7,
        )

        call_kwargs = mock_client.converse.call_args.kwargs
        assert call_kwargs["modelId"] == "eu.anthropic.claude-haiku-4-5-20251001-v1:0"

    @patch("services.bedrock.load_config")
    @patch("services.bedrock.get_bedrock_client")
    def test_invoke_model_sends_correct_message_structure(
        self, mock_get_client, mock_load_config
    ):
        """invoke_model sends messages with correct role and content structure."""
        from services.bedrock import invoke_model

        mock_config = MagicMock()
        mock_config.aws_region = "eu-west-1"
        mock_config.aws_profile = None
        mock_load_config.return_value = mock_config

        mock_client = MagicMock()
        mock_client.converse.return_value = self._make_converse_response("ok")
        mock_get_client.return_value = mock_client

        invoke_model(
            prompt="Describe a serverless API",
            model_id="eu.anthropic.claude-haiku-4-5-20251001-v1:0",
            temperature=0.5,
        )

        call_kwargs = mock_client.converse.call_args.kwargs
        assert call_kwargs["messages"] == [
            {"role": "user", "content": [{"text": "Describe a serverless API"}]}
        ]

    @patch("services.bedrock.load_config")
    @patch("services.bedrock.get_bedrock_client")
    def test_invoke_model_sends_correct_inference_config(
        self, mock_get_client, mock_load_config
    ):
        """invoke_model sends inferenceConfig with temperature and maxTokens."""
        from services.bedrock import invoke_model

        mock_config = MagicMock()
        mock_config.aws_region = "eu-west-1"
        mock_config.aws_profile = None
        mock_load_config.return_value = mock_config

        mock_client = MagicMock()
        mock_client.converse.return_value = self._make_converse_response("ok")
        mock_get_client.return_value = mock_client

        invoke_model(
            prompt="Test",
            model_id="eu.anthropic.claude-haiku-4-5-20251001-v1:0",
            temperature=0.8,
        )

        call_kwargs = mock_client.converse.call_args.kwargs
        assert call_kwargs["inferenceConfig"]["temperature"] == 0.8
        assert call_kwargs["inferenceConfig"]["maxTokens"] == 8192

    @patch("services.bedrock.load_config")
    @patch("services.bedrock.get_bedrock_client")
    def test_invoke_model_returns_response_text(
        self, mock_get_client, mock_load_config
    ):
        """invoke_model returns the text content from the Converse response."""
        from services.bedrock import invoke_model

        mock_config = MagicMock()
        mock_config.aws_region = "eu-west-1"
        mock_config.aws_profile = None
        mock_load_config.return_value = mock_config

        expected_text = '{"title": "Test Architecture"}'
        mock_client = MagicMock()
        mock_client.converse.return_value = self._make_converse_response(expected_text)
        mock_get_client.return_value = mock_client

        result = invoke_model(
            prompt="Test prompt",
            model_id="eu.anthropic.claude-haiku-4-5-20251001-v1:0",
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
        mock_config.aws_region = "eu-west-1"
        mock_config.aws_profile = None
        mock_load_config.return_value = mock_config

        mock_client = MagicMock()
        mock_client.converse.return_value = self._make_converse_response("ok")
        mock_get_client.return_value = mock_client

        invoke_model(prompt="Test", model_id="test-model", temperature=0.0)
        call_kwargs = mock_client.converse.call_args.kwargs
        assert call_kwargs["inferenceConfig"]["temperature"] == 0.0

    @patch("services.bedrock.load_config")
    @patch("services.bedrock.get_bedrock_client")
    def test_invoke_model_temperature_one(
        self, mock_get_client, mock_load_config
    ):
        """invoke_model correctly passes temperature=1.0."""
        from services.bedrock import invoke_model

        mock_config = MagicMock()
        mock_config.aws_region = "eu-west-1"
        mock_config.aws_profile = None
        mock_load_config.return_value = mock_config

        mock_client = MagicMock()
        mock_client.converse.return_value = self._make_converse_response("ok")
        mock_get_client.return_value = mock_client

        invoke_model(prompt="Test", model_id="test-model", temperature=1.0)
        call_kwargs = mock_client.converse.call_args.kwargs
        assert call_kwargs["inferenceConfig"]["temperature"] == 1.0
