"""Unit tests for pages/3_Settings.py."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def mock_streamlit():
    """Mock the streamlit module since it's not installed in the test environment."""
    mock_st = MagicMock()
    sys.modules["streamlit"] = mock_st
    yield mock_st
    del sys.modules["streamlit"]


def _load_settings_module():
    """Load the 3_Settings.py module using importlib (numeric prefix not importable normally)."""
    module_path = Path(__file__).parent.parent.parent / "pages" / "3_Settings.py"
    spec = importlib.util.spec_from_file_location("pages_3_settings", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestSettingsPage:
    """Test the Settings page rendering logic."""

    def test_displays_configured_values(
        self, monkeypatch: pytest.MonkeyPatch, mock_streamlit: MagicMock
    ) -> None:
        """Settings page displays actual env var values when set."""
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-20250514-v1:0")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        _load_settings_module()

        mock_streamlit.title.assert_called_once()
        assert "Settings" in mock_streamlit.title.call_args[0][0]

        calls = mock_streamlit.text_input.call_args_list
        assert len(calls) == 3

        # AWS Region
        assert calls[0][0][0] == "AWS Region"
        assert calls[0][1]["value"] == "us-east-1"
        assert calls[0][1]["disabled"] is True

        # Bedrock Model ID
        assert calls[1][0][0] == "Bedrock Model ID"
        assert calls[1][1]["value"] == "anthropic.claude-sonnet-4-20250514-v1:0"
        assert calls[1][1]["disabled"] is True

        # Log Level
        assert calls[2][0][0] == "Log Level"
        assert calls[2][1]["value"] == "DEBUG"
        assert calls[2][1]["disabled"] is True

    def test_displays_not_configured_when_env_vars_missing(
        self, monkeypatch: pytest.MonkeyPatch, mock_streamlit: MagicMock
    ) -> None:
        """Settings page shows 'Not configured' for missing env vars."""
        monkeypatch.delenv("AWS_REGION", raising=False)
        monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)
        monkeypatch.delenv("LOG_LEVEL", raising=False)

        _load_settings_module()

        calls = mock_streamlit.text_input.call_args_list
        assert len(calls) == 3

        # AWS Region - not set
        assert calls[0][1]["value"] == "Not configured"

        # Bedrock Model ID - not set
        assert calls[1][1]["value"] == "Not configured"

        # Log Level - defaults to INFO
        assert calls[2][1]["value"] == "INFO"

    def test_log_level_defaults_to_info(
        self, monkeypatch: pytest.MonkeyPatch, mock_streamlit: MagicMock
    ) -> None:
        """LOG_LEVEL defaults to INFO when not set."""
        monkeypatch.setenv("AWS_REGION", "eu-west-1")
        monkeypatch.setenv("BEDROCK_MODEL_ID", "some-model")
        monkeypatch.delenv("LOG_LEVEL", raising=False)

        _load_settings_module()

        calls = mock_streamlit.text_input.call_args_list
        assert calls[2][1]["value"] == "INFO"
