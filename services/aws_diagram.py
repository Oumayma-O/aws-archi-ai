"""AWS architecture diagram generator using the `diagrams` package.

Generates PNG diagrams with official AWS icons from structured architecture data.
"""

import os
import tempfile
from pathlib import Path

from models.architecture import DiagramConnection, DiagramNode


# Mapping of common aws_service strings to diagrams package classes
def _get_node_class(aws_service: str):
    """Map an AWS service name to the corresponding diagrams Node class.

    Args:
        aws_service: AWS service type string from the architecture model.

    Returns:
        A diagrams Node class.
    """
    service_lower = aws_service.lower()

    # Compute
    if any(k in service_lower for k in ["ec2", "instance"]):
        from diagrams.aws.compute import EC2
        return EC2
    if any(k in service_lower for k in ["ecs", "container"]):
        from diagrams.aws.compute import ECS
        return ECS
    if "fargate" in service_lower:
        from diagrams.aws.compute import Fargate
        return Fargate
    if "lambda" in service_lower:
        from diagrams.aws.compute import Lambda
        return Lambda
    if "batch" in service_lower:
        from diagrams.aws.compute import Batch
        return Batch

    # Storage
    if "s3" in service_lower:
        from diagrams.aws.storage import S3
        return S3
    if "efs" in service_lower:
        from diagrams.aws.storage import EFS
        return EFS
    if "ebs" in service_lower:
        from diagrams.aws.storage import EBS
        return EBS

    # Database
    if any(k in service_lower for k in ["rds", "postgres", "mysql", "aurora"]):
        from diagrams.aws.database import RDS
        return RDS
    if "dynamodb" in service_lower:
        from diagrams.aws.database import Dynamodb
        return Dynamodb
    if any(k in service_lower for k in ["elasticache", "redis", "cache"]):
        from diagrams.aws.database import ElastiCache
        return ElastiCache

    # Network
    if any(k in service_lower for k in ["cloudfront", "cdn"]):
        from diagrams.aws.network import CloudFront
        return CloudFront
    if any(k in service_lower for k in ["alb", "elb", "load balancer", "application load"]):
        from diagrams.aws.network import ALB
        return ALB
    if "nlb" in service_lower:
        from diagrams.aws.network import NLB
        return NLB
    if any(k in service_lower for k in ["route53", "route 53", "dns"]):
        from diagrams.aws.network import Route53
        return Route53
    if any(k in service_lower for k in ["api gateway", "apigateway", "api gw"]):
        from diagrams.aws.network import APIGateway
        return APIGateway
    if "vpc" in service_lower:
        from diagrams.aws.network import VPC
        return VPC
    if "nat" in service_lower:
        from diagrams.aws.network import NATGateway
        return NATGateway

    # Security
    if "waf" in service_lower:
        from diagrams.aws.security import WAF
        return WAF
    if any(k in service_lower for k in ["iam", "identity"]):
        from diagrams.aws.security import IAM
        return IAM
    if any(k in service_lower for k in ["cognito", "auth"]):
        from diagrams.aws.security import Cognito
        return Cognito
    if any(k in service_lower for k in ["kms", "key management"]):
        from diagrams.aws.security import KMS
        return KMS
    if any(k in service_lower for k in ["secrets", "secret"]):
        from diagrams.aws.security import SecretsManager
        return SecretsManager
    if "shield" in service_lower:
        from diagrams.aws.security import Shield
        return Shield

    # Integration / Messaging
    if "sqs" in service_lower:
        from diagrams.aws.integration import SQS
        return SQS
    if "sns" in service_lower:
        from diagrams.aws.integration import SNS
        return SNS
    if "eventbridge" in service_lower:
        from diagrams.aws.integration import Eventbridge
        return Eventbridge
    if "step function" in service_lower:
        from diagrams.aws.integration import StepFunctions
        return StepFunctions

    # Management
    if "cloudwatch" in service_lower:
        from diagrams.aws.management import Cloudwatch
        return Cloudwatch
    if "cloudtrail" in service_lower:
        from diagrams.aws.management import Cloudtrail
        return Cloudtrail
    if "cloudformation" in service_lower:
        from diagrams.aws.management import Cloudformation
        return Cloudformation

    # Analytics
    if "kinesis" in service_lower:
        from diagrams.aws.analytics import KinesisDataStreams
        return KinesisDataStreams
    if "athena" in service_lower:
        from diagrams.aws.analytics import Athena
        return Athena
    if "glue" in service_lower:
        from diagrams.aws.analytics import Glue
        return Glue

    # ML
    if "sagemaker" in service_lower:
        from diagrams.aws.ml import Sagemaker
        return Sagemaker
    if "bedrock" in service_lower:
        from diagrams.aws.ml import Sagemaker  # No Bedrock icon yet, use Sagemaker
        return Sagemaker

    # Notification / Email
    if "ses" in service_lower:
        from diagrams.aws.engagement import SES
        return SES

    # Generic / Client
    if any(k in service_lower for k in ["client", "user", "browser"]):
        from diagrams.aws.general import Users
        return Users

    # Default fallback
    from diagrams.aws.general import GenericDatabase
    return GenericDatabase


def generate_aws_diagram(
    nodes: list[DiagramNode],
    connections: list[DiagramConnection],
    title: str = "AWS Architecture",
) -> bytes | None:
    """Generate a PNG diagram with official AWS icons.

    Args:
        nodes: List of diagram nodes with id, label, aws_service.
        connections: List of connections with source_id, target_id, optional label.
        title: Diagram title.

    Returns:
        PNG image bytes, or None if generation fails.
    """
    if not nodes:
        return None

    # Create temp file for output
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "architecture")

        try:
            from diagrams import Diagram, Edge

            with Diagram(
                title,
                filename=output_path,
                show=False,
                direction="TB",
                graph_attr={"bgcolor": "white", "pad": "0.5"},
            ):
                # Create node instances
                node_map = {}
                for node in nodes:
                    NodeClass = _get_node_class(node.aws_service)
                    node_map[node.id] = NodeClass(node.label)

                # Create connections
                node_ids = set(node_map.keys())
                for conn in connections:
                    if conn.source_id in node_ids and conn.target_id in node_ids:
                        src = node_map[conn.source_id]
                        dst = node_map[conn.target_id]
                        if conn.label:
                            src >> Edge(label=conn.label) >> dst
                        else:
                            src >> dst

            # Read the generated PNG
            png_path = output_path + ".png"
            if os.path.exists(png_path):
                return Path(png_path).read_bytes()

        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Diagram generation failed: {e}")
            return None

    return None
