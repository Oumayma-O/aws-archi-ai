"""Shared test fixtures for AWS Architect AI test suite."""

import json
from unittest.mock import MagicMock, patch

import pytest

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
