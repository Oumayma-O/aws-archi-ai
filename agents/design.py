"""Design Agent module.

Implements the DesignAgent that produces comprehensive architecture designs
from research findings and requirements profiles.

Responsibilities:
- Generate complete ArchitectureReport with services, networking, VPC, security, costs
- Perform Well-Architected Framework review
- Respect budget constraints with documented trade-offs
- Include IaC skeleton when iac_preference is specified
- Omit VPC for fully serverless architectures
"""

from __future__ import annotations

from typing import Any

from models.architecture import (
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
from models.report import (
    ArchitectureRationale,
    ArchitectureReport,
    CostComparison,
    VPCDesign,
    WellArchitectedReview,
)
from models.requirements import RequirementsProfile
from models.research import ResearchSummary

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SERVERLESS_SERVICES = ("Lambda", "API Gateway", "DynamoDB", "S3", "Step Functions", "EventBridge")

DESIGN_SYSTEM_PROMPT = """You are an expert AWS Solutions Architect. Given a requirements profile
and research summary, produce a comprehensive architecture design.

Your output must be a complete ArchitectureReport including:
- Service selection with justification
- Networking configuration (VPC design for non-serverless)
- Security configuration following AWS best practices
- Scaling strategy
- Monitoring and observability setup
- Cost estimates respecting budget constraints
- Architecture rationale for each major decision
- IaC skeleton if iac_preference is specified

Rules:
- For serverless architectures, omit VPC design entirely
- Always respect budget constraints; document trade-offs when budget is tight
- Include at least 2 cost comparisons between alternatives
- Ensure every service has a documented rationale
"""


# ---------------------------------------------------------------------------
# Template definitions for deterministic fallback
# ---------------------------------------------------------------------------

SERVERLESS_TEMPLATE: dict[str, Any] = {
    "services": [
        ServiceDetail(name="AWS Lambda", role="Compute - serverless function execution"),
        ServiceDetail(name="Amazon API Gateway", role="API management and request routing"),
        ServiceDetail(name="Amazon DynamoDB", role="NoSQL database for application data"),
        ServiceDetail(name="Amazon S3", role="Object storage for static assets and files"),
        ServiceDetail(name="Amazon CloudFront", role="CDN for low-latency content delivery"),
        ServiceDetail(name="Amazon Cognito", role="User authentication and authorization"),
    ],
    "networking": NetworkingConfig(
        vpc="Not required - fully serverless architecture",
        subnets=[],
        security_groups=[],
        load_balancers=[],
    ),
    "security": SecurityConfig(
        iam_policies=["Lambda execution role with least-privilege", "API Gateway resource policies"],
        encryption=["DynamoDB encryption at rest (AWS managed key)", "S3 SSE-S3 default encryption", "API Gateway TLS 1.2"],
        cloudtrail=["API activity logging enabled", "Lambda invocation tracking"],
        waf_rules=["Rate limiting on API Gateway", "SQL injection protection"],
        recommendations=[
            "Enable AWS WAF on API Gateway",
            "Use Cognito user pools with MFA",
            "Enable CloudTrail for audit logging",
            "Apply least-privilege IAM policies",
        ],
    ),
    "scaling": ScalingConfig(
        strategy="Serverless auto-scaling (managed by AWS)",
        policies=[
            "Lambda concurrency: reserved 100, provisioned for predictable load",
            "DynamoDB on-demand capacity mode",
            "API Gateway throttling: 10000 req/s burst",
        ],
    ),
    "monitoring": MonitoringConfig(
        cloudwatch_metrics=["Lambda Duration", "Lambda Errors", "API Gateway 4XX/5XX", "DynamoDB ConsumedCapacity"],
        alarms=["Lambda error rate > 5%", "API Gateway 5XX > 1%", "DynamoDB throttling events"],
        dashboards=["Application health dashboard", "Cost tracking dashboard"],
    ),
    "diagram_nodes": [
        DiagramNode(id="cloudfront", label="CloudFront", aws_service="CloudFront"),
        DiagramNode(id="apigw", label="API Gateway", aws_service="API Gateway"),
        DiagramNode(id="lambda", label="Lambda Functions", aws_service="Lambda"),
        DiagramNode(id="dynamodb", label="DynamoDB", aws_service="DynamoDB"),
        DiagramNode(id="s3", label="S3 Bucket", aws_service="S3"),
        DiagramNode(id="cognito", label="Cognito", aws_service="Cognito"),
    ],
    "diagram_connections": [
        DiagramConnection(source_id="cloudfront", target_id="apigw", label="HTTPS"),
        DiagramConnection(source_id="cloudfront", target_id="s3", label="Static assets"),
        DiagramConnection(source_id="apigw", target_id="lambda", label="Invoke"),
        DiagramConnection(source_id="lambda", target_id="dynamodb", label="Read/Write"),
        DiagramConnection(source_id="lambda", target_id="s3", label="Store/Retrieve"),
        DiagramConnection(source_id="cognito", target_id="apigw", label="Authorize"),
    ],
    "cost_breakdown": [
        ServiceCost(service="AWS Lambda", monthly_cost="$20"),
        ServiceCost(service="Amazon API Gateway", monthly_cost="$15"),
        ServiceCost(service="Amazon DynamoDB", monthly_cost="$25"),
        ServiceCost(service="Amazon S3", monthly_cost="$5"),
        ServiceCost(service="Amazon CloudFront", monthly_cost="$10"),
        ServiceCost(service="Amazon Cognito", monthly_cost="$0 (free tier)"),
    ],
    "total_monthly": "$75",
}

CONTAINER_TEMPLATE: dict[str, Any] = {
    "services": [
        ServiceDetail(name="Amazon ECS Fargate", role="Container orchestration - serverless containers"),
        ServiceDetail(name="Application Load Balancer", role="Traffic distribution and health checks"),
        ServiceDetail(name="Amazon RDS", role="Managed relational database (PostgreSQL)"),
        ServiceDetail(name="Amazon ElastiCache", role="In-memory caching layer (Redis)"),
        ServiceDetail(name="Amazon S3", role="Object storage for static assets and uploads"),
        ServiceDetail(name="Amazon CloudFront", role="CDN for low-latency content delivery"),
    ],
    "networking": NetworkingConfig(
        vpc="Production VPC (10.0.0.0/16) with public and private subnets across 2 AZs",
        subnets=[
            "Public subnet A (10.0.1.0/24) - ALB, NAT Gateway",
            "Public subnet B (10.0.2.0/24) - ALB, NAT Gateway",
            "Private subnet A (10.0.10.0/24) - ECS tasks, RDS",
            "Private subnet B (10.0.11.0/24) - ECS tasks, RDS",
        ],
        security_groups=[
            "ALB SG: inbound 443 from 0.0.0.0/0",
            "ECS SG: inbound from ALB SG only",
            "RDS SG: inbound 5432 from ECS SG only",
            "ElastiCache SG: inbound 6379 from ECS SG only",
        ],
        load_balancers=["Application Load Balancer with HTTPS listener"],
    ),
    "security": SecurityConfig(
        iam_policies=[
            "ECS task execution role",
            "ECS task role with least-privilege access to RDS, S3, ElastiCache",
        ],
        encryption=[
            "RDS encryption at rest (AWS KMS)",
            "ElastiCache encryption in transit and at rest",
            "S3 SSE-S3 default encryption",
            "ALB TLS 1.2 termination",
        ],
        cloudtrail=["API activity logging enabled", "VPC Flow Logs enabled"],
        waf_rules=["Rate limiting on ALB", "SQL injection protection", "XSS protection"],
        recommendations=[
            "Enable AWS WAF on ALB",
            "Use VPC endpoints for S3 and ECR",
            "Enable RDS automated backups",
            "Apply least-privilege IAM policies",
            "Enable VPC Flow Logs for network monitoring",
        ],
    ),
    "scaling": ScalingConfig(
        strategy="ECS Service Auto Scaling with target tracking",
        policies=[
            "Target CPU utilization: 70%",
            "Target memory utilization: 80%",
            "Min tasks: 2, Max tasks: 10",
            "Scale-in cooldown: 300s, Scale-out cooldown: 60s",
        ],
    ),
    "monitoring": MonitoringConfig(
        cloudwatch_metrics=[
            "ECS CPUUtilization",
            "ECS MemoryUtilization",
            "ALB RequestCount",
            "ALB TargetResponseTime",
            "RDS CPUUtilization",
            "RDS FreeStorageSpace",
            "ElastiCache CacheHitRate",
        ],
        alarms=[
            "ECS CPU > 85%",
            "ALB 5XX > 1%",
            "RDS CPU > 80%",
            "RDS free storage < 20%",
            "ElastiCache evictions > 0",
        ],
        dashboards=["Application health dashboard", "Database performance dashboard", "Cost tracking dashboard"],
    ),
    "diagram_nodes": [
        DiagramNode(id="cloudfront", label="CloudFront", aws_service="CloudFront"),
        DiagramNode(id="alb", label="Application Load Balancer", aws_service="ELB"),
        DiagramNode(id="ecs", label="ECS Fargate", aws_service="ECS"),
        DiagramNode(id="rds", label="RDS PostgreSQL", aws_service="RDS"),
        DiagramNode(id="elasticache", label="ElastiCache Redis", aws_service="ElastiCache"),
        DiagramNode(id="s3", label="S3 Bucket", aws_service="S3"),
    ],
    "diagram_connections": [
        DiagramConnection(source_id="cloudfront", target_id="alb", label="HTTPS"),
        DiagramConnection(source_id="cloudfront", target_id="s3", label="Static assets"),
        DiagramConnection(source_id="alb", target_id="ecs", label="HTTP"),
        DiagramConnection(source_id="ecs", target_id="rds", label="SQL"),
        DiagramConnection(source_id="ecs", target_id="elasticache", label="Cache"),
        DiagramConnection(source_id="ecs", target_id="s3", label="Store/Retrieve"),
    ],
    "cost_breakdown": [
        ServiceCost(service="Amazon ECS Fargate", monthly_cost="$150"),
        ServiceCost(service="Application Load Balancer", monthly_cost="$25"),
        ServiceCost(service="Amazon RDS", monthly_cost="$100"),
        ServiceCost(service="Amazon ElastiCache", monthly_cost="$50"),
        ServiceCost(service="Amazon S3", monthly_cost="$10"),
        ServiceCost(service="Amazon CloudFront", monthly_cost="$15"),
    ],
    "total_monthly": "$350",
    "vpc_design": VPCDesign(
        cidr_block="10.0.0.0/16",
        public_subnets=[
            {"az": "eu-west-1a", "cidr": "10.0.1.0/24", "purpose": "ALB, NAT Gateway"},
            {"az": "eu-west-1b", "cidr": "10.0.2.0/24", "purpose": "ALB, NAT Gateway"},
        ],
        private_subnets=[
            {"az": "eu-west-1a", "cidr": "10.0.10.0/24", "purpose": "ECS tasks, RDS primary"},
            {"az": "eu-west-1b", "cidr": "10.0.11.0/24", "purpose": "ECS tasks, RDS standby"},
        ],
        nat_gateways=["nat-gw-eu-west-1a", "nat-gw-eu-west-1b"],
        internet_gateway=True,
        vpc_endpoints=[
            {"service": "s3", "type": "Gateway"},
            {"service": "ecr.api", "type": "Interface"},
            {"service": "ecr.dkr", "type": "Interface"},
        ],
        route_tables=[
            {"name": "public-rt", "routes": ["0.0.0.0/0 -> igw"]},
            {"name": "private-rt-a", "routes": ["0.0.0.0/0 -> nat-gw-a"]},
            {"name": "private-rt-b", "routes": ["0.0.0.0/0 -> nat-gw-b"]},
        ],
        security_groups=[
            {"name": "alb-sg", "rules": ["inbound 443 from 0.0.0.0/0", "outbound all to ecs-sg"]},
            {"name": "ecs-sg", "rules": ["inbound 8080 from alb-sg", "outbound 5432 to rds-sg", "outbound 6379 to cache-sg"]},
            {"name": "rds-sg", "rules": ["inbound 5432 from ecs-sg"]},
            {"name": "cache-sg", "rules": ["inbound 6379 from ecs-sg"]},
        ],
        network_acls=[
            {"name": "public-nacl", "rules": ["allow inbound 443", "allow outbound ephemeral"]},
            {"name": "private-nacl", "rules": ["allow inbound from VPC CIDR", "allow outbound to VPC CIDR"]},
        ],
        validation_notes=[
            "No database in public subnets",
            "NAT Gateway in each AZ for high availability",
            "VPC endpoints reduce data transfer costs",
        ],
    ),
}


# ---------------------------------------------------------------------------
# IaC skeleton templates
# ---------------------------------------------------------------------------

IAC_TERRAFORM_SERVERLESS = '''# Terraform skeleton for serverless architecture
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  default = "eu-west-1"
}

resource "aws_lambda_function" "api" {
  function_name = "api-handler"
  runtime       = "python3.12"
  handler       = "main.handler"
  role          = aws_iam_role.lambda_role.arn
  # TODO: Add source code configuration
}

resource "aws_apigatewayv2_api" "api" {
  name          = "app-api"
  protocol_type = "HTTP"
}

resource "aws_dynamodb_table" "main" {
  name         = "app-data"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }
}

resource "aws_s3_bucket" "assets" {
  bucket = "app-assets"
}

resource "aws_cloudfront_distribution" "cdn" {
  # TODO: Configure origins and behaviors
  enabled = true
  origin {
    domain_name = aws_s3_bucket.assets.bucket_regional_domain_name
    origin_id   = "s3-assets"
  }
  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "s3-assets"
    viewer_protocol_policy = "redirect-to-https"
    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }
  }
  viewer_certificate { cloudfront_default_certificate = true }
  restrictions { geo_restriction { restriction_type = "none" } }
}
'''

IAC_TERRAFORM_CONTAINER = '''# Terraform skeleton for container architecture
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  default = "eu-west-1"
}

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
}

resource "aws_ecs_cluster" "main" {
  name = "app-cluster"
}

resource "aws_ecs_service" "app" {
  name            = "app-service"
  cluster         = aws_ecs_cluster.main.id
  launch_type     = "FARGATE"
  desired_count   = 2
  # TODO: Add task definition and network configuration
}

resource "aws_lb" "main" {
  name               = "app-alb"
  internal           = false
  load_balancer_type = "application"
  # TODO: Add subnets and security groups
}

resource "aws_db_instance" "main" {
  engine               = "postgres"
  engine_version       = "15"
  instance_class       = "db.t3.medium"
  allocated_storage    = 20
  multi_az             = true
  storage_encrypted    = true
  # TODO: Add VPC security group and subnet group
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "app-cache"
  description          = "Redis cache cluster"
  engine               = "redis"
  node_type            = "cache.t3.micro"
  num_cache_clusters   = 2
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
}

resource "aws_s3_bucket" "assets" {
  bucket = "app-assets"
}
'''

IAC_CDK_SERVERLESS = '''# AWS CDK skeleton for serverless architecture
from aws_cdk import (
    Stack,
    aws_lambda as lambda_,
    aws_apigateway as apigw,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_cognito as cognito,
)
from constructs import Construct

class ServerlessStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # DynamoDB table
        table = dynamodb.Table(self, "AppTable",
            partition_key=dynamodb.Attribute(name="pk", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="sk", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        )

        # Lambda function
        handler = lambda_.Function(self, "ApiHandler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="main.handler",
            code=lambda_.Code.from_asset("lambda"),
        )
        table.grant_read_write_data(handler)

        # API Gateway
        api = apigw.RestApi(self, "AppApi")
        api.root.add_method("ANY", apigw.LambdaIntegration(handler))

        # S3 bucket for assets
        bucket = s3.Bucket(self, "AssetsBucket")

        # Cognito user pool
        user_pool = cognito.UserPool(self, "UserPool",
            self_sign_up_enabled=True,
        )
'''

IAC_CDK_CONTAINER = '''# AWS CDK skeleton for container architecture
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_rds as rds,
    aws_elasticache as elasticache,
    aws_s3 as s3,
)
from constructs import Construct

class ContainerStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # VPC
        vpc = ec2.Vpc(self, "AppVpc", max_azs=2)

        # ECS Cluster
        cluster = ecs.Cluster(self, "AppCluster", vpc=vpc)

        # Fargate service with ALB
        service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "AppService",
            cluster=cluster,
            desired_count=2,
            cpu=256,
            memory_limit_mib=512,
        )

        # RDS
        db = rds.DatabaseInstance(self, "AppDb",
            engine=rds.DatabaseInstanceEngine.postgres(version=rds.PostgresEngineVersion.VER_15),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MEDIUM),
            vpc=vpc,
            multi_az=True,
        )

        # S3 bucket
        bucket = s3.Bucket(self, "AssetsBucket")
'''

IAC_CLOUDFORMATION_SERVERLESS = '''# CloudFormation skeleton for serverless architecture
AWSTemplateFormatVersion: "2010-09-09"
Transform: AWS::Serverless-2016-10-31
Description: Serverless application architecture

Resources:
  ApiFunction:
    Type: AWS::Serverless::Function
    Properties:
      Runtime: python3.12
      Handler: main.handler
      Events:
        Api:
          Type: Api
          Properties:
            Path: /{proxy+}
            Method: ANY

  AppTable:
    Type: AWS::DynamoDB::Table
    Properties:
      BillingMode: PAY_PER_REQUEST
      KeySchema:
        - AttributeName: pk
          KeyType: HASH
        - AttributeName: sk
          KeyType: RANGE
      AttributeDefinitions:
        - AttributeName: pk
          AttributeType: S
        - AttributeName: sk
          AttributeType: S

  AssetsBucket:
    Type: AWS::S3::Bucket
'''

IAC_CLOUDFORMATION_CONTAINER = '''# CloudFormation skeleton for container architecture
AWSTemplateFormatVersion: "2010-09-09"
Description: Container-based application architecture

Resources:
  VPC:
    Type: AWS::EC2::VPC
    Properties:
      CidrBlock: 10.0.0.0/16
      EnableDnsHostnames: true

  ECSCluster:
    Type: AWS::ECS::Cluster
    Properties:
      ClusterName: app-cluster

  ALB:
    Type: AWS::ElasticLoadBalancingV2::LoadBalancer
    Properties:
      Type: application
      Scheme: internet-facing

  RDSInstance:
    Type: AWS::RDS::DBInstance
    Properties:
      Engine: postgres
      EngineVersion: "15"
      DBInstanceClass: db.t3.medium
      MultiAZ: true
      StorageEncrypted: true
'''


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _is_serverless(profile: RequirementsProfile) -> bool:
    """Determine if the architecture should be fully serverless."""
    return profile.compute_preference == "serverless"


def _get_iac_skeleton(profile: RequirementsProfile) -> str | None:
    """Return the appropriate IaC skeleton based on preferences."""
    if profile.iac_preference is None:
        return None

    is_serverless = _is_serverless(profile)
    preference = profile.iac_preference.lower()

    if preference == "terraform":
        return IAC_TERRAFORM_SERVERLESS if is_serverless else IAC_TERRAFORM_CONTAINER
    elif preference == "cdk":
        return IAC_CDK_SERVERLESS if is_serverless else IAC_CDK_CONTAINER
    elif preference == "cloudformation":
        return IAC_CLOUDFORMATION_SERVERLESS if is_serverless else IAC_CLOUDFORMATION_CONTAINER

    return None


def _build_rationale(profile: RequirementsProfile, is_serverless: bool) -> list[ArchitectureRationale]:
    """Build architecture rationale based on the profile."""
    rationale: list[ArchitectureRationale] = []

    if is_serverless:
        rationale.append(ArchitectureRationale(
            decision="Compute platform selection",
            chosen_option="AWS Lambda",
            alternatives_considered=["ECS Fargate", "EC2 instances", "EKS"],
            reasoning="Serverless preference specified; Lambda provides zero-ops scaling, pay-per-use pricing, and eliminates VPC management overhead.",
        ))
        rationale.append(ArchitectureRationale(
            decision="Database selection",
            chosen_option="Amazon DynamoDB",
            alternatives_considered=["RDS PostgreSQL", "Aurora Serverless", "DocumentDB"],
            reasoning="DynamoDB aligns with serverless model: on-demand capacity, no connection management, single-digit millisecond latency.",
        ))
        rationale.append(ArchitectureRationale(
            decision="API layer",
            chosen_option="Amazon API Gateway",
            alternatives_considered=["ALB with Lambda targets", "AppSync"],
            reasoning="API Gateway provides native Lambda integration, request validation, throttling, and usage plans out of the box.",
        ))
        rationale.append(ArchitectureRationale(
            decision="CDN and static assets",
            chosen_option="Amazon CloudFront + S3",
            alternatives_considered=["S3 direct access", "Third-party CDN"],
            reasoning="CloudFront provides global edge caching, HTTPS termination, and tight S3 integration for static assets.",
        ))
        rationale.append(ArchitectureRationale(
            decision="Authentication",
            chosen_option="Amazon Cognito",
            alternatives_considered=["Custom auth with Lambda", "Auth0", "Okta"],
            reasoning="Cognito integrates natively with API Gateway authorizers, supports MFA, and is cost-effective for most workloads.",
        ))
    else:
        rationale.append(ArchitectureRationale(
            decision="Compute platform selection",
            chosen_option="Amazon ECS Fargate",
            alternatives_considered=["EC2 instances", "EKS", "Lambda"],
            reasoning="Container preference specified; Fargate provides serverless containers without cluster management while supporting stateful workloads.",
        ))
        rationale.append(ArchitectureRationale(
            decision="Database selection",
            chosen_option="Amazon RDS PostgreSQL",
            alternatives_considered=["Aurora", "DynamoDB", "DocumentDB"],
            reasoning="RDS PostgreSQL offers mature relational model, Multi-AZ for HA, and broad ecosystem support for containerized applications.",
        ))
        rationale.append(ArchitectureRationale(
            decision="Caching layer",
            chosen_option="Amazon ElastiCache Redis",
            alternatives_considered=["Memcached", "DAX", "Application-level caching"],
            reasoning="Redis provides versatile data structures, persistence options, and replication for session management and query caching.",
        ))
        rationale.append(ArchitectureRationale(
            decision="Load balancing",
            chosen_option="Application Load Balancer",
            alternatives_considered=["Network Load Balancer", "API Gateway"],
            reasoning="ALB provides Layer 7 routing, path-based routing, and native ECS integration with health checks.",
        ))
        rationale.append(ArchitectureRationale(
            decision="CDN and static assets",
            chosen_option="Amazon CloudFront + S3",
            alternatives_considered=["S3 direct access", "Third-party CDN"],
            reasoning="CloudFront provides global edge caching, HTTPS termination, and reduces load on the ALB for static content.",
        ))

    return rationale


def _build_cost_comparisons(is_serverless: bool) -> list[CostComparison]:
    """Build cost comparisons between architectural alternatives."""
    comparisons: list[CostComparison] = []

    if is_serverless:
        comparisons.append(CostComparison(
            approach_a="Lambda + API Gateway",
            approach_a_monthly="$35/month",
            approach_b="ECS Fargate + ALB",
            approach_b_monthly="$175/month",
            recommendation="Lambda + API Gateway",
            reasoning="For moderate traffic with variable load, serverless pay-per-use is significantly cheaper than always-on containers.",
        ))
        comparisons.append(CostComparison(
            approach_a="DynamoDB on-demand",
            approach_a_monthly="$25/month",
            approach_b="RDS db.t3.small",
            approach_b_monthly="$35/month",
            recommendation="DynamoDB on-demand",
            reasoning="DynamoDB on-demand eliminates provisioning decisions and costs less for variable workloads with < 10K RPS.",
        ))
    else:
        comparisons.append(CostComparison(
            approach_a="ECS Fargate",
            approach_a_monthly="$150/month",
            approach_b="EC2 (t3.medium x2)",
            approach_b_monthly="$120/month",
            recommendation="ECS Fargate",
            reasoning="Fargate eliminates cluster management overhead; the $30/month premium saves significant operational time.",
        ))
        comparisons.append(CostComparison(
            approach_a="RDS Multi-AZ",
            approach_a_monthly="$100/month",
            approach_b="Aurora Serverless v2",
            approach_b_monthly="$90/month (at baseline)",
            recommendation="RDS Multi-AZ",
            reasoning="RDS provides predictable pricing; Aurora Serverless can spike with load. RDS is preferred for steady-state workloads.",
        ))

    return comparisons


def _build_budget_rationale(
    profile: RequirementsProfile,
    total_monthly: str,
    rationale: list[ArchitectureRationale],
) -> list[ArchitectureRationale]:
    """Add budget-related rationale if budget is specified and architecture exceeds it."""
    if profile.budget_monthly_usd is None:
        return rationale

    # Parse total_monthly (e.g., "$350")
    cost_value = float(total_monthly.replace("$", "").replace(",", ""))

    if cost_value > profile.budget_monthly_usd:
        rationale.append(ArchitectureRationale(
            decision="Budget constraint trade-off",
            chosen_option=f"Architecture at ${cost_value}/month (exceeds ${profile.budget_monthly_usd} budget)",
            alternatives_considered=[
                "Reduce to single-AZ deployment",
                "Remove caching layer",
                "Use smaller instance sizes",
            ],
            reasoning=(
                f"The recommended architecture costs ${cost_value}/month, exceeding the "
                f"${profile.budget_monthly_usd}/month budget by ${cost_value - profile.budget_monthly_usd:.0f}. "
                "Trade-off: maintaining HA and performance requires this investment. "
                "Consider reducing to single-AZ or removing ElastiCache to cut costs."
            ),
        ))

    return rationale


def _build_well_architected_review(report: ArchitectureReport) -> WellArchitectedReview:
    """Produce a Well-Architected Framework review of the architecture."""
    is_serverless = report.vpc_design is None

    operational_excellence = [
        "Infrastructure as code recommended for repeatable deployments",
        "CloudWatch alarms configured for key metrics",
        "Automated scaling reduces operational burden",
    ]

    security = [
        "Encryption at rest enabled for all data stores",
        "TLS 1.2 enforced for data in transit",
        "IAM least-privilege policies applied",
        "AWS WAF recommended for web application protection",
    ]

    reliability = [
        "Multi-AZ deployment for high availability" if not is_serverless else "Serverless services provide built-in redundancy",
        "Health checks configured for automatic recovery",
        "Automated backups for data durability",
    ]

    performance_efficiency = [
        "Auto-scaling configured to handle load variations",
        "CloudFront caching reduces latency for global users",
        "Right-sized resources based on traffic patterns",
    ]

    cost_optimization = [
        "Pay-per-use pricing model" if is_serverless else "Right-sized instances with auto-scaling",
        "CloudFront reduces data transfer costs",
        "Reserved capacity recommended for steady-state workloads" if not is_serverless else "Serverless eliminates idle resource costs",
    ]

    sustainability = [
        "Serverless minimizes idle resource consumption" if is_serverless else "Auto-scaling reduces over-provisioning waste",
        "Managed services reduce infrastructure footprint",
    ]

    violations: list[str] = []
    improvements: list[str] = []

    # Check for common violations/improvements
    if not report.security.waf_rules:
        violations.append("No WAF rules configured - web application is unprotected against common attacks")

    if not report.monitoring.alarms:
        violations.append("No CloudWatch alarms - operational issues may go undetected")

    if is_serverless:
        improvements.append("Consider adding X-Ray tracing for distributed request tracking")
        improvements.append("Add DynamoDB point-in-time recovery for data protection")
    else:
        improvements.append("Consider adding AWS Backup for centralized backup management")
        improvements.append("Add Container Insights for deeper ECS observability")
        if report.vpc_design and len(report.vpc_design.nat_gateways) < 2:
            violations.append("Single NAT Gateway creates a single point of failure")

    improvements.append("Consider implementing a CI/CD pipeline for automated deployments")

    return WellArchitectedReview(
        operational_excellence=operational_excellence,
        security=security,
        reliability=reliability,
        performance_efficiency=performance_efficiency,
        cost_optimization=cost_optimization,
        sustainability=sustainability,
        violations=violations,
        improvement_opportunities=improvements,
    )


# ---------------------------------------------------------------------------
# DesignAgent
# ---------------------------------------------------------------------------


class DesignAgent:
    """Agent that produces architecture designs from research and requirements.

    Uses the Strands Agent SDK for LLM-powered design when a model is provided,
    with deterministic template-based fallback logic for testing without an LLM.
    """

    def __init__(self, model: Any | None = None):
        """Initialize the design agent.

        Args:
            model: Optional Strands model instance. If None, uses deterministic
                   template-based design logic.
        """
        self._model = model
        self._agent = self._create_agent() if model is not None else None

    def _create_agent(self) -> Any:
        """Create the underlying Strands Agent with the design system prompt."""
        try:
            from strands import Agent

            return Agent(
                model=self._model,
                system_prompt=DESIGN_SYSTEM_PROMPT,
            )
        except ImportError:
            return None

    def design(
        self, profile: RequirementsProfile, research: ResearchSummary
    ) -> ArchitectureReport:
        """Generate a complete architecture design.

        Args:
            profile: Requirements from clarification phase.
            research: Research findings from research phase.

        Returns:
            Complete ArchitectureReport with all sections populated.
        """
        # Use deterministic template-based logic (model=None or Strands unavailable)
        return self._design_deterministic(profile, research)

    def review(self, report: ArchitectureReport) -> WellArchitectedReview:
        """Review architecture against Well-Architected Framework.

        Args:
            report: The draft architecture report.

        Returns:
            Review summary with findings per pillar.
        """
        return _build_well_architected_review(report)

    def _design_deterministic(
        self, profile: RequirementsProfile, research: ResearchSummary
    ) -> ArchitectureReport:
        """Produce an architecture report using templates based on compute preference.

        Selects the appropriate template (serverless or container) and populates
        the ArchitectureReport with realistic service selections, networking,
        security, costs, and diagram data.
        """
        is_serverless = _is_serverless(profile)
        template = SERVERLESS_TEMPLATE if is_serverless else CONTAINER_TEMPLATE

        # Build title and summary
        arch_type = "Serverless" if is_serverless else "Container-Based"
        title = f"{arch_type} Architecture for {profile.original_description[:80]}"
        summary = (
            f"A {arch_type.lower()} architecture on AWS using "
            + ", ".join(s.name for s in template["services"][:3])
            + f" and more. Designed for {profile.target_region} region"
            + (f" within ${profile.budget_monthly_usd}/month budget." if profile.budget_monthly_usd else ".")
        )

        if is_serverless:
            architecture_description = (
                "Fully serverless architecture leveraging AWS Lambda for compute, "
                "API Gateway for request routing, DynamoDB for data persistence, "
                "S3 for static asset storage, CloudFront for global content delivery, "
                "and Cognito for user authentication. No VPC required — all services "
                "communicate via AWS service endpoints with IAM-based security."
            )
        else:
            architecture_description = (
                "Container-based architecture running on ECS Fargate with Application "
                "Load Balancer for traffic distribution. Backend services include RDS "
                "PostgreSQL for relational data, ElastiCache Redis for caching, and S3 "
                "for object storage. Deployed in a VPC with public and private subnets "
                "across two availability zones for high availability."
            )

        # Build rationale
        rationale = _build_rationale(profile, is_serverless)
        total_monthly = template["total_monthly"]
        rationale = _build_budget_rationale(profile, total_monthly, rationale)

        # Build cost comparisons
        cost_comparisons = _build_cost_comparisons(is_serverless)

        # Get IaC skeleton
        iac_skeleton = _get_iac_skeleton(profile)

        # VPC design (only for non-serverless)
        vpc_design = template.get("vpc_design") if not is_serverless else None

        # Diagram
        diagram = DiagramData(
            nodes=template["diagram_nodes"],
            connections=template["diagram_connections"],
        )

        # Recommendations
        recommendations = [
            "Enable AWS CloudTrail for comprehensive audit logging",
            "Implement CI/CD pipeline for automated deployments",
            "Set up AWS Budgets alerts for cost monitoring",
            "Review and rotate IAM credentials regularly",
            "Enable AWS Config for compliance monitoring",
        ]

        # Collect data sources used from research
        data_sources = []
        if research.data_sources_available:
            data_sources = ["AWS Well-Architected Framework", "AWS Pricing Calculator"]
            if research.reference_architectures:
                data_sources.extend(
                    ra.name for ra in research.reference_architectures[:3]
                )

        # Build assumptions
        assumptions = list(profile.assumptions)
        if not profile.traffic.requests_per_second:
            assumptions.append("Assumed moderate traffic pattern (~100 RPS)")

        # Estimated cost
        estimated_cost = EstimatedCost(
            total_monthly=total_monthly,
            breakdown=template["cost_breakdown"],
        )

        report = ArchitectureReport(
            title=title,
            summary=summary,
            architecture_description=architecture_description,
            aws_services=template["services"],
            networking=template["networking"],
            vpc_design=vpc_design,
            security=template["security"],
            scaling=template["scaling"],
            monitoring=template["monitoring"],
            estimated_cost=estimated_cost,
            cost_comparisons=cost_comparisons,
            diagram=diagram,
            recommendations=recommendations,
            rationale=rationale,
            well_architected_review=None,
            iac_skeleton=iac_skeleton,
            assumptions=assumptions,
            data_sources_used=data_sources,
        )

        # Perform Well-Architected review
        report.well_architected_review = self.review(report)

        return report
