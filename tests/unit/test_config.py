"""Unit tests for utils/config.py and services/exceptions.py."""

import os

import pytest

from services.exceptions import (
    ArchitectAIError,
    BedrockConnectionError,
    BedrockThrottlingError,
    BedrockTimeoutError,
    ConfigurationError,
    DiagramRenderError,
    JsonExtractionError,
)
from utils.config import AppConfig, load_config


class TestExceptionHierarchy:
    """Test that all custom exceptions inherit from ArchitectAIError."""

    def test_bedrock_connection_error_inherits(self) -> None:
        err = BedrockConnectionError("connection failed")
        assert isinstance(err, ArchitectAIError)
        assert isinstance(err, Exception)

    def test_bedrock_throttling_error_inherits(self) -> None:
        err = BedrockThrottlingError("throttled")
        assert isinstance(err, ArchitectAIError)

    def test_bedrock_timeout_error_inherits(self) -> None:
        err = BedrockTimeoutError("timeout")
        assert isinstance(err, ArchitectAIError)

    def test_json_extraction_error_inherits(self) -> None:
        err = JsonExtractionError("no json")
        assert isinstance(err, ArchitectAIError)

    def test_diagram_render_error_inherits(self) -> None:
        err = DiagramRenderError("render failed")
        assert isinstance(err, ArchitectAIError)

    def test_configuration_error_inherits(self) -> None:
        err = ConfigurationError("missing var")
        assert isinstance(err, ArchitectAIError)

    def test_exception_message_preserved(self) -> None:
        msg = "Missing required configuration: AWS_REGION"
        err = ConfigurationError(msg)
        assert str(err) == msg


class TestAppConfig:
    """Test the AppConfig Pydantic model."""

    def test_valid_config_all_fields(self) -> None:
        config = AppConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            aws_profile="my-profile",
            log_level="DEBUG",
        )
        assert config.aws_region == "us-east-1"
        assert config.bedrock_model_id == "anthropic.claude-sonnet-4-20250514-v1:0"
        assert config.aws_profile == "my-profile"
        assert config.log_level == "DEBUG"

    def test_optional_fields_defaults(self) -> None:
        config = AppConfig(
            aws_region="eu-west-1",
            bedrock_model_id="some-model",
        )
        assert config.aws_profile is None
        assert config.log_level == "INFO"


class TestLoadConfig:
    """Test load_config() function."""

    def test_loads_all_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AWS_REGION", "us-west-2")
        monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-20250514-v1:0")
        monkeypatch.setenv("AWS_PROFILE", "dev")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        config = load_config()

        assert config.aws_region == "us-west-2"
        assert config.bedrock_model_id == "anthropic.claude-sonnet-4-20250514-v1:0"
        assert config.aws_profile == "dev"
        assert config.log_level == "DEBUG"

    def test_optional_vars_use_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        monkeypatch.setenv("BEDROCK_MODEL_ID", "some-model")
        monkeypatch.delenv("AWS_PROFILE", raising=False)
        monkeypatch.delenv("LOG_LEVEL", raising=False)

        config = load_config()

        assert config.aws_profile is None
        assert config.log_level == "INFO"

    def test_raises_when_aws_region_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AWS_REGION", raising=False)
        monkeypatch.setenv("BEDROCK_MODEL_ID", "some-model")

        with pytest.raises(ConfigurationError, match="AWS_REGION"):
            load_config()

    def test_raises_when_bedrock_model_id_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)

        with pytest.raises(ConfigurationError, match="BEDROCK_MODEL_ID"):
            load_config()

    def test_raises_when_both_required_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AWS_REGION", raising=False)
        monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)

        with pytest.raises(ConfigurationError, match="AWS_REGION") as exc_info:
            load_config()
        assert "BEDROCK_MODEL_ID" in str(exc_info.value)

    def test_empty_string_treated_as_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AWS_REGION", "")
        monkeypatch.setenv("BEDROCK_MODEL_ID", "some-model")

        with pytest.raises(ConfigurationError, match="AWS_REGION"):
            load_config()
