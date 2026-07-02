"""Application configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

from services.exceptions import ConfigurationError

# Load .env file from project root (ensures env vars are available
# regardless of which Streamlit page triggers the import first)
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")


class AppConfig(BaseModel):
    """Application configuration from environment variables."""

    aws_region: str
    bedrock_model_id: str
    aws_profile: str | None = None
    log_level: str = "INFO"


def load_config() -> AppConfig:
    """
    Load configuration from environment variables.

    Reads AWS_REGION, BEDROCK_MODEL_ID (required), AWS_PROFILE, and
    LOG_LEVEL (optional) from the process environment.

    Returns:
        Validated AppConfig instance.

    Raises:
        ConfigurationError: If required variables are missing.
    """
    missing: list[str] = []

    aws_region = os.environ.get("AWS_REGION")
    if not aws_region:
        missing.append("AWS_REGION")

    bedrock_model_id = os.environ.get("BEDROCK_MODEL_ID")
    if not bedrock_model_id:
        missing.append("BEDROCK_MODEL_ID")

    if missing:
        raise ConfigurationError(
            f"Missing required configuration: {', '.join(missing)}"
        )

    return AppConfig(
        aws_region=aws_region,  # type: ignore[arg-type]
        bedrock_model_id=bedrock_model_id,  # type: ignore[arg-type]
        aws_profile=os.environ.get("AWS_PROFILE"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
