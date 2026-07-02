"""Amazon Bedrock client service for AWS Architect AI.

Uses the Converse Stream API for progressive output with prompt-based JSON.
Supports streaming for real-time UI updates.
"""

import json
import logging
from collections.abc import Generator
from functools import lru_cache
from typing import Any

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import (
    ClientError,
    ConnectionError,
    EndpointConnectionError,
    ReadTimeoutError,
)

from services.exceptions import (
    BedrockConnectionError,
    BedrockThrottlingError,
    BedrockTimeoutError,
)
from utils.config import load_config

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_bedrock_client(region: str, profile: str | None = None) -> Any:
    """Get or create a cached Bedrock runtime client.

    Args:
        region: AWS region name.
        profile: Optional AWS profile name.

    Returns:
        boto3 Bedrock runtime client instance.
    """
    session_kwargs: dict[str, str] = {"region_name": region}
    if profile:
        session_kwargs["profile_name"] = profile

    session = boto3.Session(**session_kwargs)
    boto_config = BotoConfig(read_timeout=120, connect_timeout=60)
    client = session.client("bedrock-runtime", config=boto_config)
    return client


def invoke_model(
    prompt: str,
    model_id: str,
    temperature: float,
    timeout: int = 120,
) -> str:
    """Send a prompt to Amazon Bedrock and return the full response text.

    Non-streaming version for backward compatibility.

    Args:
        prompt: The complete prompt string.
        model_id: Bedrock model identifier.
        temperature: Generation temperature (0.0-1.0).
        timeout: Request timeout in seconds.

    Returns:
        Raw response text from the model.

    Raises:
        BedrockTimeoutError: If the request exceeds timeout.
        BedrockConnectionError: If connection to Bedrock fails.
        BedrockThrottlingError: If the request is throttled.
    """
    config = load_config()
    client = get_bedrock_client(region=config.aws_region, profile=config.aws_profile)

    logger.info(
        "Invoking Bedrock model: model_id=%s, request_size=%d",
        model_id,
        len(prompt),
    )

    try:
        response = client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 8192, "temperature": temperature},
        )
    except ReadTimeoutError as exc:
        raise BedrockTimeoutError(
            f"Request to Bedrock timed out after {timeout} seconds."
        ) from exc
    except EndpointConnectionError as exc:
        raise BedrockConnectionError(
            f"Failed to connect to Amazon Bedrock endpoint: {exc}"
        ) from exc
    except ConnectionError as exc:
        raise BedrockConnectionError(
            f"Connection error while contacting Amazon Bedrock: {exc}"
        ) from exc
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code == "ThrottlingException":
            raise BedrockThrottlingError(
                "Request was throttled by AWS. Please wait and try again."
            ) from exc
        raise BedrockConnectionError(
            f"AWS client error: {error_code} - {exc}"
        ) from exc

    content_blocks = response["output"]["message"]["content"]
    return "".join(
        block.get("text", "") for block in content_blocks if "text" in block
    )


def invoke_model_stream(
    prompt: str,
    model_id: str,
    temperature: float,
) -> Generator[str, None, None]:
    """Send a prompt to Bedrock and yield response chunks as they arrive.

    Uses converse_stream for real-time progressive output.

    Args:
        prompt: The complete prompt string.
        model_id: Bedrock model identifier.
        temperature: Generation temperature (0.0-1.0).

    Yields:
        Text chunks as they arrive from the model.

    Raises:
        BedrockTimeoutError: If the request exceeds timeout.
        BedrockConnectionError: If connection to Bedrock fails.
        BedrockThrottlingError: If the request is throttled.
    """
    config = load_config()
    client = get_bedrock_client(region=config.aws_region, profile=config.aws_profile)

    logger.info(
        "Invoking Bedrock model (streaming): model_id=%s, request_size=%d",
        model_id,
        len(prompt),
    )

    try:
        response = client.converse_stream(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 8192, "temperature": temperature},
        )
    except ReadTimeoutError as exc:
        raise BedrockTimeoutError(
            "Request to Bedrock timed out."
        ) from exc
    except EndpointConnectionError as exc:
        raise BedrockConnectionError(
            f"Failed to connect to Amazon Bedrock endpoint: {exc}"
        ) from exc
    except ConnectionError as exc:
        raise BedrockConnectionError(
            f"Connection error while contacting Amazon Bedrock: {exc}"
        ) from exc
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code == "ThrottlingException":
            raise BedrockThrottlingError(
                "Request was throttled by AWS. Please wait and try again."
            ) from exc
        raise BedrockConnectionError(
            f"AWS client error: {error_code} - {exc}"
        ) from exc

    for event in response["stream"]:
        if "contentBlockDelta" in event:
            chunk = event["contentBlockDelta"]["delta"].get("text", "")
            if chunk:
                yield chunk
