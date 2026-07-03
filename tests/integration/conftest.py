"""Integration test fixtures for AWS Architect AI agentic features.

Provides fixtures for testing the full agent workflow with
mocked external services (DynamoDB via moto, MCP servers).
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import boto3
import pytest


@pytest.fixture
def aws_credentials():
    """Mock AWS credentials for moto-based tests."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "eu-west-1"
    yield
    # Cleanup is handled by moto context managers


@pytest.fixture
def dynamodb_table(aws_credentials):
    """Create a moto-mocked DynamoDB table for session persistence testing.

    Uses lazy import of moto to avoid import errors if moto is not installed.
    """
    try:
        from moto import mock_aws
    except ImportError:
        pytest.skip("moto not installed - skipping DynamoDB integration tests")

    with mock_aws():
        client = boto3.client("dynamodb", region_name="eu-west-1")
        client.create_table(
            TableName="architect-sessions",
            KeySchema=[
                {"AttributeName": "session_id", "KeyType": "HASH"},
            ],
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
                    "ProvisionedThroughput": {
                        "ReadCapacityUnits": 5,
                        "WriteCapacityUnits": 5,
                    },
                }
            ],
            ProvisionedThroughput={
                "ReadCapacityUnits": 5,
                "WriteCapacityUnits": 5,
            },
        )

        table = boto3.resource("dynamodb", region_name="eu-west-1").Table(
            "architect-sessions"
        )
        yield table
