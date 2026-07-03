"""Shared test fixtures for AWS Architect AI test suite."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import settings, HealthCheck

from models.architecture import (
    ArchitectureModel,
    DiagramConnection,
    DiagramData,
    DiagramNode,
    EstimatedCost,
    MonitoringConfig,
    NetworkingConfig,
    ScalingConfig,
    SecurityConfig,
    ServiceCost,
    ServiceDetail,
)


# ---------------------------------------------------------------------------
# Hypothesis profile configuration
# ---------------------------------------------------------------------------
settings.register_profile(
    "default",
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.register_profile(
    "ci",
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile("default")


@pytest.fixture
def sample_architecture() -> ArchitectureModel:
    """A full valid ArchitectureModel instance for testing."""
    return ArchitectureModel(
        title="E-Commerce Platform Architecture",
        summary="A scalable e-commerce platform using AWS managed services.",
        architecture_description=(
            "This architecture uses ECS Fargate for the application tier, "
            "RDS Aurora for the database, and CloudFront for content delivery. "
            "All traffic passes through an ALB with WAF protection."
        ),
        aws_services=[
            ServiceDetail(name="Amazon ECS", role="Container orchestration for application services"),
            ServiceDetail(name="Amazon RDS Aurora", role="Managed relational database"),
            ServiceDetail(name="Amazon CloudFront", role="CDN for static assets"),
            ServiceDetail(name="Amazon S3", role="Object storage for static files"),
        ],
        networking=NetworkingConfig(
            vpc="10.0.0.0/16 VPC with public and private subnets across 2 AZs",
            subnets=["Public subnet 10.0.1.0/24", "Private subnet 10.0.2.0/24"],
            security_groups=["ALB SG: inbound 80/443", "ECS SG: inbound from ALB"],
            load_balancers=["Application Load Balancer in public subnets"],
        ),
        security=SecurityConfig(
            iam_policies=["ECS task role with minimal permissions"],
            encryption=["RDS encryption at rest with KMS", "TLS 1.2 in transit"],
            cloudtrail=["CloudTrail enabled for API auditing"],
            waf_rules=["Rate limiting rule", "SQL injection protection"],
            recommendations=["Enable MFA for IAM users", "Rotate credentials regularly"],
        ),
        scaling=ScalingConfig(
            strategy="Horizontal scaling with ECS service auto-scaling",
            policies=["Target tracking on CPU utilization at 70%"],
        ),
        monitoring=MonitoringConfig(
            cloudwatch_metrics=["CPUUtilization", "MemoryUtilization", "RequestCount"],
            alarms=["High CPU alarm at 85%", "5xx error rate alarm"],
            dashboards=["Application health dashboard"],
        ),
        estimated_cost=EstimatedCost(
            total_monthly="$250-$500/month",
            breakdown=[
                ServiceCost(service="Amazon ECS", monthly_cost="$80-$150/month"),
                ServiceCost(service="Amazon RDS Aurora", monthly_cost="$100-$200/month"),
                ServiceCost(service="Amazon CloudFront", monthly_cost="$20-$50/month"),
                ServiceCost(service="Amazon S3", monthly_cost="$5-$10/month"),
            ],
        ),
        diagram=DiagramData(
            nodes=[
                DiagramNode(id="cloudfront", label="CloudFront CDN", aws_service="CloudFront"),
                DiagramNode(id="alb", label="Application Load Balancer", aws_service="ALB"),
                DiagramNode(id="ecs", label="ECS Fargate Service", aws_service="ECS"),
                DiagramNode(id="rds", label="Aurora Database", aws_service="RDS"),
                DiagramNode(id="s3", label="Static Assets", aws_service="S3"),
            ],
            connections=[
                DiagramConnection(source_id="cloudfront", target_id="alb", label="HTTPS"),
                DiagramConnection(source_id="alb", target_id="ecs", label="HTTP"),
                DiagramConnection(source_id="ecs", target_id="rds", label="SQL queries"),
                DiagramConnection(source_id="cloudfront", target_id="s3", label=None),
            ],
        ),
        recommendations=[
            "Enable multi-AZ deployment for RDS",
            "Use ElastiCache for session management",
            "Implement CI/CD pipeline with CodePipeline",
        ],
    )


@pytest.fixture
def sample_architecture_json(sample_architecture: ArchitectureModel) -> str:
    """The JSON string representation of sample_architecture."""
    return sample_architecture.model_dump_json()


@pytest.fixture
def mock_bedrock_client():
    """A mocked boto3 bedrock-runtime client."""
    client = MagicMock()
    client.invoke_model = MagicMock()
    return client


# ---------------------------------------------------------------------------
# Agentic Architect fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_requirements_profile():
    """A complete RequirementsProfile instance for testing agentic features.

    Uses lazy import since models/requirements.py may not exist yet during
    early development phases.
    """
    from models.requirements import (
        ComplianceRequirement,
        RequirementsProfile,
        TrafficPattern,
    )

    return RequirementsProfile(
        original_description=(
            "I need a scalable e-commerce platform that handles 10K concurrent users "
            "with PCI-DSS compliance and multi-region failover."
        ),
        compute_preference="containers",
        budget_monthly_usd=2500.0,
        compliance=ComplianceRequirement(
            frameworks=["PCI-DSS", "SOC2"],
            data_residency="eu-west-1",
            encryption_requirements=["AES-256 at rest", "TLS 1.2 in transit"],
        ),
        multi_region=True,
        disaster_recovery="warm-standby",
        traffic=TrafficPattern(
            peak_concurrent_users=10000,
            requests_per_second=5000,
            data_transfer_gb_monthly=500.0,
            pattern="spiky",
        ),
        storage_requirements=["S3 for assets", "RDS for transactional data", "ElastiCache for sessions"],
        authentication="cognito",
        high_availability=True,
        additional_constraints=["Must support blue-green deployments"],
        assumptions=[],
        target_region="eu-west-1",
        iac_preference="cdk",
    )


@pytest.fixture
def mock_docs_mcp():
    """A MagicMock for the AWS Docs MCP client.

    Simulates the MCPClient interface used by the Research Agent
    to query AWS documentation and reference architectures.
    """
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    # Mock the call method for tool invocations
    mock_client.call_tool = AsyncMock(
        return_value={
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "reference_architectures": [
                            {
                                "name": "E-Commerce on AWS",
                                "description": "Scalable e-commerce reference architecture",
                                "url": "https://aws.amazon.com/solutions/e-commerce/",
                            }
                        ],
                        "best_practices": [
                            "Use ALB for HTTP/HTTPS traffic distribution",
                            "Deploy across multiple AZs for high availability",
                        ],
                    }),
                }
            ]
        }
    )

    # Mock list_tools for discovery
    mock_client.list_tools = AsyncMock(
        return_value=[
            {"name": "search_docs", "description": "Search AWS documentation"},
            {"name": "get_reference_architecture", "description": "Get reference architectures"},
            {"name": "get_waf_guidance", "description": "Get Well-Architected guidance"},
        ]
    )

    return mock_client


@pytest.fixture
def mock_pricing_mcp():
    """A MagicMock for the Pricing MCP client.

    Simulates the MCPClient interface used by the Research Agent
    to query AWS pricing data and service cost comparisons.
    """
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    mock_client.call_tool = AsyncMock(
        return_value={
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "pricing": {
                            "service": "Amazon ECS",
                            "region": "eu-west-1",
                            "monthly_estimate": "$150.00",
                            "free_tier_eligible": False,
                            "pricing_model": "per-vCPU-hour",
                        }
                    }),
                }
            ]
        }
    )

    mock_client.list_tools = AsyncMock(
        return_value=[
            {"name": "get_pricing", "description": "Get service pricing"},
            {"name": "compare_pricing", "description": "Compare service pricing options"},
            {"name": "estimate_monthly", "description": "Estimate monthly costs"},
        ]
    )

    return mock_client


@pytest.fixture
def mock_drawio_mcp():
    """A MagicMock for the Draw.io MCP client.

    Simulates the MCPClient interface used by the Diagram Agent
    to generate professional Draw.io diagrams with AWS icons.
    """
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    sample_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<mxGraphModel><root>'
        '<mxCell id="0"/>'
        '<mxCell id="1" parent="0"/>'
        '<mxCell id="2" value="ECS" style="shape=mxgraph.aws4.ecs" '
        'vertex="1" parent="1"><mxGeometry x="100" y="100" width="60" height="60"/></mxCell>'
        '</root></mxGraphModel>'
    )

    mock_client.call_tool = AsyncMock(
        return_value={
            "content": [
                {
                    "type": "text",
                    "text": sample_xml,
                }
            ]
        }
    )

    mock_client.list_tools = AsyncMock(
        return_value=[
            {"name": "generate_diagram", "description": "Generate Draw.io diagram"},
            {"name": "add_aws_icons", "description": "Add AWS icons to diagram"},
            {"name": "export_png", "description": "Export diagram as PNG"},
        ]
    )

    return mock_client


@pytest.fixture
def mock_dynamodb_table():
    """A mock DynamoDB table resource for session store testing.

    Uses MagicMock to simulate boto3 DynamoDB Table operations.
    For full integration testing, use moto fixtures instead.
    """
    table = MagicMock()
    table.put_item = MagicMock(return_value={"ResponseMetadata": {"HTTPStatusCode": 200}})
    table.get_item = MagicMock(return_value={"Item": None})
    table.query = MagicMock(return_value={"Items": [], "Count": 0})
    table.delete_item = MagicMock(return_value={"ResponseMetadata": {"HTTPStatusCode": 200}})
    return table
