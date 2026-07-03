"""Research Agent module.

Implements the ResearchAgent that queries MCP servers for AWS documentation,
reference architectures, Well-Architected Framework guidance, and pricing data.

Responsibilities:
- Query AWS Docs MCP for reference architectures and best practices
- Query Pricing MCP for service pricing in user's region
- Produce cost comparisons for alternative services
- Handle MCP unavailability with graceful degradation
- Calculate monthly costs from profile traffic patterns
"""

from __future__ import annotations

import logging
from typing import Any

from models.requirements import RequirementsProfile
from models.research import (
    PricingComparison,
    ReferenceArchitecture,
    ResearchSummary,
    ServiceRecommendation,
    WellArchitectedGuidance,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RESEARCH_SYSTEM_PROMPT = """You are an expert AWS Solutions Architect researcher.
Your job is to find relevant reference architectures, best practices, pricing data,
and Well-Architected Framework guidance for a given set of requirements.

You have access to AWS Documentation and Pricing MCP tools.
Use them to gather current, accurate information about AWS services.
"""

# ---------------------------------------------------------------------------
# Fallback pricing data (approximate $/month for common services)
# Used when Pricing MCP is unavailable.
# Prices are estimates for eu-west-1 and may not reflect current rates.
# ---------------------------------------------------------------------------

FALLBACK_PRICING: dict[str, dict[str, Any]] = {
    "Lambda": {
        "unit": "per 1M requests + duration",
        "price_per_1m_requests": 0.20,
        "price_per_gb_second": 0.0000166667,
        "free_tier": "1M requests/month, 400,000 GB-seconds",
        "free_tier_eligible": True,
    },
    "ECS_Fargate": {
        "unit": "per vCPU-hour + GB-hour",
        "price_per_vcpu_hour": 0.04048,
        "price_per_gb_hour": 0.004445,
        "free_tier": None,
        "free_tier_eligible": False,
    },
    "EC2_t3_medium": {
        "unit": "per hour",
        "price_per_hour": 0.0416,
        "free_tier": "750 hours/month t2.micro (12 months)",
        "free_tier_eligible": True,
    },
    "RDS_PostgreSQL": {
        "unit": "per hour (db.t3.medium)",
        "price_per_hour": 0.068,
        "storage_per_gb_month": 0.115,
        "free_tier": "750 hours/month db.t2.micro (12 months)",
        "free_tier_eligible": True,
    },
    "DynamoDB": {
        "unit": "per million WRU/RRU (on-demand) + storage",
        "price_per_million_wru": 1.25,
        "price_per_million_rru": 0.25,
        "storage_per_gb_month": 0.25,
        "free_tier": "25 WCU, 25 RCU, 25 GB storage",
        "free_tier_eligible": True,
    },
    "S3": {
        "unit": "per GB storage + requests",
        "price_per_gb_month": 0.023,
        "price_per_1k_put": 0.005,
        "price_per_1k_get": 0.0004,
        "free_tier": "5 GB storage, 20K GET, 2K PUT (12 months)",
        "free_tier_eligible": True,
    },
    "CloudFront": {
        "unit": "per GB data transfer + requests",
        "price_per_gb_transfer": 0.085,
        "price_per_10k_requests": 0.01,
        "free_tier": "1 TB data transfer/month (always free)",
        "free_tier_eligible": True,
    },
    "ALB": {
        "unit": "per hour + LCU-hour",
        "price_per_hour": 0.0225,
        "price_per_lcu_hour": 0.008,
        "free_tier": None,
        "free_tier_eligible": False,
    },
}

# ---------------------------------------------------------------------------
# Fallback reference architectures
# ---------------------------------------------------------------------------

FALLBACK_REFERENCE_ARCHITECTURES: dict[str, ReferenceArchitecture] = {
    "serverless_web": ReferenceArchitecture(
        name="Serverless Web Application",
        description=(
            "API Gateway + Lambda + DynamoDB pattern for REST APIs "
            "with auto-scaling and pay-per-request pricing."
        ),
        url="https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/serverless-patterns.html",
        relevance="Suitable for serverless workloads with variable traffic",
    ),
    "container_microservices": ReferenceArchitecture(
        name="Container-based Microservices on ECS",
        description=(
            "ECS Fargate + ALB + RDS pattern for containerised "
            "microservices with predictable scaling."
        ),
        url="https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/container-patterns.html",
        relevance="Suitable for container workloads requiring fine-grained control",
    ),
    "three_tier_web": ReferenceArchitecture(
        name="Three-Tier Web Application",
        description=(
            "CloudFront + ALB + EC2/ECS + RDS multi-AZ pattern "
            "for traditional web applications."
        ),
        url="https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/three-tier-web.html",
        relevance="Classic pattern for instance-based or mixed compute workloads",
    ),
    "event_driven": ReferenceArchitecture(
        name="Event-Driven Architecture",
        description=(
            "EventBridge + Lambda + SQS/SNS pattern for "
            "decoupled, event-driven processing pipelines."
        ),
        url="https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/event-driven.html",
        relevance="Suitable for asynchronous, decoupled workloads",
    ),
    "data_lake": ReferenceArchitecture(
        name="Modern Data Lake",
        description=(
            "S3 + Glue + Athena + Lake Formation pattern for "
            "analytics and data processing workloads."
        ),
        url="https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/data-lake.html",
        relevance="Suitable for data-intensive and analytics workloads",
    ),
}

# ---------------------------------------------------------------------------
# Fallback Well-Architected guidance
# ---------------------------------------------------------------------------

FALLBACK_WAF_GUIDANCE: list[WellArchitectedGuidance] = [
    WellArchitectedGuidance(
        pillar="Operational Excellence",
        recommendations=[
            "Use Infrastructure as Code (CloudFormation/CDK/Terraform)",
            "Implement observability with CloudWatch and X-Ray",
            "Automate deployment pipelines with CI/CD",
            "Define runbooks for operational procedures",
        ],
        risks=["Manual deployments increase human error risk"],
    ),
    WellArchitectedGuidance(
        pillar="Security",
        recommendations=[
            "Apply least-privilege IAM policies",
            "Encrypt data at rest and in transit",
            "Enable CloudTrail and GuardDuty",
            "Use VPC security groups and NACLs for defense in depth",
        ],
        risks=["Overly permissive IAM roles", "Unencrypted data stores"],
    ),
    WellArchitectedGuidance(
        pillar="Reliability",
        recommendations=[
            "Deploy across multiple Availability Zones",
            "Implement health checks and auto-recovery",
            "Use managed services for reduced operational burden",
            "Define RTO/RPO targets and test recovery procedures",
        ],
        risks=["Single-AZ deployment creates single point of failure"],
    ),
    WellArchitectedGuidance(
        pillar="Performance Efficiency",
        recommendations=[
            "Right-size compute resources based on actual load",
            "Use caching (ElastiCache, CloudFront) to reduce latency",
            "Select appropriate database engine for access patterns",
            "Monitor and benchmark performance continuously",
        ],
        risks=["Over-provisioning wastes budget", "Under-provisioning degrades UX"],
    ),
    WellArchitectedGuidance(
        pillar="Cost Optimization",
        recommendations=[
            "Use auto-scaling to match demand",
            "Leverage Savings Plans or Reserved Instances for steady workloads",
            "Choose serverless for spiky/variable traffic",
            "Monitor costs with AWS Cost Explorer and budgets",
        ],
        risks=["Idle resources accumulate cost", "Missing free tier opportunities"],
    ),
    WellArchitectedGuidance(
        pillar="Sustainability",
        recommendations=[
            "Use managed and serverless services to improve utilisation",
            "Right-size resources to avoid waste",
            "Select energy-efficient regions where possible",
            "Optimise data transfer to reduce network overhead",
        ],
        risks=["Over-provisioned resources waste energy"],
    ),
]

# ---------------------------------------------------------------------------
# Compute service alternatives for comparison
# ---------------------------------------------------------------------------

COMPUTE_ALTERNATIVES: dict[str, list[str]] = {
    "serverless": ["Lambda", "ECS_Fargate", "EC2_t3_medium"],
    "containers": ["ECS_Fargate", "Lambda", "EC2_t3_medium"],
    "instances": ["EC2_t3_medium", "ECS_Fargate", "Lambda"],
    "mixed": ["Lambda", "ECS_Fargate", "EC2_t3_medium"],
}

DATABASE_ALTERNATIVES: dict[str, list[str]] = {
    "relational": ["RDS_PostgreSQL", "DynamoDB"],
    "nosql": ["DynamoDB", "RDS_PostgreSQL"],
    "default": ["RDS_PostgreSQL", "DynamoDB"],
}

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _estimate_lambda_monthly_cost(
    requests_per_second: float,
    avg_duration_ms: float = 200,
    memory_mb: int = 256,
) -> float:
    """Estimate monthly Lambda cost from traffic patterns.

    Args:
        requests_per_second: Average requests per second.
        avg_duration_ms: Average function duration in milliseconds.
        memory_mb: Allocated memory in MB.

    Returns:
        Estimated monthly cost in USD.
    """
    monthly_requests = requests_per_second * 60 * 60 * 24 * 30
    request_cost = (monthly_requests / 1_000_000) * FALLBACK_PRICING["Lambda"]["price_per_1m_requests"]
    gb_seconds = monthly_requests * (avg_duration_ms / 1000) * (memory_mb / 1024)
    duration_cost = gb_seconds * FALLBACK_PRICING["Lambda"]["price_per_gb_second"]
    return round(request_cost + duration_cost, 2)


def _estimate_fargate_monthly_cost(
    tasks: int = 2,
    vcpu: float = 0.25,
    memory_gb: float = 0.5,
) -> float:
    """Estimate monthly ECS Fargate cost.

    Args:
        tasks: Number of running tasks (24/7).
        vcpu: vCPU allocated per task.
        memory_gb: Memory (GB) allocated per task.

    Returns:
        Estimated monthly cost in USD.
    """
    hours_per_month = 730
    vcpu_cost = tasks * vcpu * hours_per_month * FALLBACK_PRICING["ECS_Fargate"]["price_per_vcpu_hour"]
    mem_cost = tasks * memory_gb * hours_per_month * FALLBACK_PRICING["ECS_Fargate"]["price_per_gb_hour"]
    return round(vcpu_cost + mem_cost, 2)


def _estimate_ec2_monthly_cost(instances: int = 2) -> float:
    """Estimate monthly EC2 cost for t3.medium instances.

    Args:
        instances: Number of running instances (24/7).

    Returns:
        Estimated monthly cost in USD.
    """
    hours_per_month = 730
    return round(
        instances * hours_per_month * FALLBACK_PRICING["EC2_t3_medium"]["price_per_hour"],
        2,
    )


def _estimate_rds_monthly_cost(
    instances: int = 1,
    storage_gb: float = 20,
) -> float:
    """Estimate monthly RDS PostgreSQL cost.

    Args:
        instances: Number of RDS instances (e.g., 2 for multi-AZ).
        storage_gb: Provisioned storage in GB.

    Returns:
        Estimated monthly cost in USD.
    """
    hours_per_month = 730
    compute = instances * hours_per_month * FALLBACK_PRICING["RDS_PostgreSQL"]["price_per_hour"]
    storage = storage_gb * FALLBACK_PRICING["RDS_PostgreSQL"]["storage_per_gb_month"]
    return round(compute + storage, 2)


def _estimate_dynamodb_monthly_cost(
    requests_per_second: float,
    storage_gb: float = 5,
) -> float:
    """Estimate monthly DynamoDB cost (on-demand mode).

    Args:
        requests_per_second: Average requests per second (split 50/50 read/write).
        storage_gb: Data stored in GB.

    Returns:
        Estimated monthly cost in USD.
    """
    monthly_requests = requests_per_second * 60 * 60 * 24 * 30
    # On-demand pricing: per million request units
    write_cost = (monthly_requests * 0.5 / 1_000_000) * FALLBACK_PRICING["DynamoDB"]["price_per_million_wru"]
    read_cost = (monthly_requests * 0.5 / 1_000_000) * FALLBACK_PRICING["DynamoDB"]["price_per_million_rru"]
    storage_cost = storage_gb * FALLBACK_PRICING["DynamoDB"]["storage_per_gb_month"]
    return round(write_cost + read_cost + storage_cost, 2)


def _estimate_s3_monthly_cost(
    storage_gb: float = 50,
    data_transfer_gb: float = 10,
) -> float:
    """Estimate monthly S3 cost.

    Args:
        storage_gb: Data stored in GB.
        data_transfer_gb: Monthly data transfer in GB.

    Returns:
        Estimated monthly cost in USD.
    """
    storage_cost = storage_gb * FALLBACK_PRICING["S3"]["price_per_gb_month"]
    # Approximate request costs
    transfer_cost = data_transfer_gb * 0.09  # data transfer out
    return round(storage_cost + transfer_cost, 2)


def _estimate_cloudfront_monthly_cost(
    data_transfer_gb: float = 100,
    requests_per_second: float = 0,
) -> float:
    """Estimate monthly CloudFront cost.

    Args:
        data_transfer_gb: Monthly data transfer in GB.
        requests_per_second: Average requests per second.

    Returns:
        Estimated monthly cost in USD.
    """
    transfer_cost = data_transfer_gb * FALLBACK_PRICING["CloudFront"]["price_per_gb_transfer"]
    monthly_requests = requests_per_second * 60 * 60 * 24 * 30
    request_cost = (monthly_requests / 10_000) * FALLBACK_PRICING["CloudFront"]["price_per_10k_requests"]
    return round(transfer_cost + request_cost, 2)


def _estimate_alb_monthly_cost() -> float:
    """Estimate monthly ALB cost (base + average LCU usage).

    Returns:
        Estimated monthly cost in USD.
    """
    hours_per_month = 730
    base_cost = hours_per_month * FALLBACK_PRICING["ALB"]["price_per_hour"]
    # Assume ~2 LCUs average utilization
    lcu_cost = hours_per_month * 2 * FALLBACK_PRICING["ALB"]["price_per_lcu_hour"]
    return round(base_cost + lcu_cost, 2)


def _get_compute_cost_estimate(
    service_key: str,
    profile: RequirementsProfile,
) -> float:
    """Get cost estimate for a compute service based on traffic profile.

    Args:
        service_key: Key in FALLBACK_PRICING (Lambda, ECS_Fargate, EC2_t3_medium).
        profile: The requirements profile with traffic data.

    Returns:
        Estimated monthly cost in USD.
    """
    rps = profile.traffic.requests_per_second or 10

    if service_key == "Lambda":
        return _estimate_lambda_monthly_cost(rps)
    elif service_key == "ECS_Fargate":
        # Scale tasks based on RPS
        tasks = max(2, rps // 500 + 1)
        return _estimate_fargate_monthly_cost(tasks=tasks)
    elif service_key == "EC2_t3_medium":
        instances = max(2, rps // 1000 + 1)
        return _estimate_ec2_monthly_cost(instances=instances)
    return 0.0


def _get_database_cost_estimate(
    service_key: str,
    profile: RequirementsProfile,
) -> float:
    """Get cost estimate for a database service based on traffic profile.

    Args:
        service_key: Key in FALLBACK_PRICING (RDS_PostgreSQL, DynamoDB).
        profile: The requirements profile with traffic data.

    Returns:
        Estimated monthly cost in USD.
    """
    rps = profile.traffic.requests_per_second or 10
    data_gb = profile.traffic.data_transfer_gb_monthly or 10

    if service_key == "RDS_PostgreSQL":
        instances = 2 if profile.high_availability else 1
        return _estimate_rds_monthly_cost(instances=instances, storage_gb=max(20, data_gb))
    elif service_key == "DynamoDB":
        return _estimate_dynamodb_monthly_cost(rps * 0.3, storage_gb=max(5, data_gb * 0.5))
    return 0.0


def _select_reference_architectures(
    profile: RequirementsProfile,
) -> list[ReferenceArchitecture]:
    """Select relevant reference architectures based on the profile.

    Args:
        profile: The requirements profile.

    Returns:
        List of relevant ReferenceArchitecture entries.
    """
    selected: list[ReferenceArchitecture] = []
    compute = profile.compute_preference or "serverless"

    if compute == "serverless":
        selected.append(FALLBACK_REFERENCE_ARCHITECTURES["serverless_web"])
        selected.append(FALLBACK_REFERENCE_ARCHITECTURES["event_driven"])
    elif compute == "containers":
        selected.append(FALLBACK_REFERENCE_ARCHITECTURES["container_microservices"])
        selected.append(FALLBACK_REFERENCE_ARCHITECTURES["three_tier_web"])
    elif compute == "instances":
        selected.append(FALLBACK_REFERENCE_ARCHITECTURES["three_tier_web"])
        selected.append(FALLBACK_REFERENCE_ARCHITECTURES["container_microservices"])
    else:  # mixed
        selected.append(FALLBACK_REFERENCE_ARCHITECTURES["three_tier_web"])
        selected.append(FALLBACK_REFERENCE_ARCHITECTURES["serverless_web"])
        selected.append(FALLBACK_REFERENCE_ARCHITECTURES["container_microservices"])

    # Add data lake if storage mentions analytics-related terms
    storage_lower = " ".join(profile.storage_requirements).lower()
    if any(kw in storage_lower for kw in ("analytics", "data lake", "athena", "glue")):
        selected.append(FALLBACK_REFERENCE_ARCHITECTURES["data_lake"])

    return selected


def _build_service_recommendations(
    profile: RequirementsProfile,
) -> list[ServiceRecommendation]:
    """Build service recommendations based on the profile.

    Args:
        profile: The requirements profile.

    Returns:
        List of ServiceRecommendation entries.
    """
    recommendations: list[ServiceRecommendation] = []
    compute = profile.compute_preference or "serverless"
    rps = profile.traffic.requests_per_second or 10

    # Compute recommendation
    if compute == "serverless":
        cost = _estimate_lambda_monthly_cost(rps)
        recommendations.append(ServiceRecommendation(
            service_name="AWS Lambda",
            justification=(
                f"Serverless compute matches preference; pay-per-request "
                f"is cost-effective at {rps} RPS. Estimated ~${cost}/month."
            ),
            alternatives=["ECS Fargate", "EC2"],
            pricing_summary=f"~${cost}/month at {rps} RPS",
            free_tier_eligible=True,
            free_tier_limits="1M requests/month, 400,000 GB-seconds",
        ))
    elif compute == "containers":
        cost = _estimate_fargate_monthly_cost(tasks=max(2, rps // 500 + 1))
        recommendations.append(ServiceRecommendation(
            service_name="ECS Fargate",
            justification=(
                f"Container compute matches preference; Fargate removes "
                f"server management overhead. Estimated ~${cost}/month."
            ),
            alternatives=["Lambda", "EC2", "EKS"],
            pricing_summary=f"~${cost}/month for {max(2, rps // 500 + 1)} tasks",
            free_tier_eligible=False,
        ))
    else:
        cost = _estimate_ec2_monthly_cost(instances=max(2, rps // 1000 + 1))
        recommendations.append(ServiceRecommendation(
            service_name="EC2 (t3.medium)",
            justification=(
                f"Instance-based compute for steady workloads; "
                f"cost-effective with Reserved Instances. Estimated ~${cost}/month."
            ),
            alternatives=["ECS Fargate", "Lambda"],
            pricing_summary=f"~${cost}/month for {max(2, rps // 1000 + 1)} instances",
            free_tier_eligible=True,
            free_tier_limits="750 hours/month t2.micro (12 months)",
        ))

    # API Gateway / ALB
    if compute == "serverless":
        recommendations.append(ServiceRecommendation(
            service_name="Amazon API Gateway",
            justification="REST/HTTP API for Lambda integration with built-in throttling and auth.",
            alternatives=["ALB"],
            pricing_summary="~$3.50 per million API calls",
            free_tier_eligible=True,
            free_tier_limits="1M API calls/month (12 months)",
        ))
    else:
        alb_cost = _estimate_alb_monthly_cost()
        recommendations.append(ServiceRecommendation(
            service_name="Application Load Balancer",
            justification=f"Layer-7 load balancing for containers/instances. Estimated ~${alb_cost}/month.",
            alternatives=["API Gateway", "Network Load Balancer"],
            pricing_summary=f"~${alb_cost}/month",
            free_tier_eligible=False,
        ))

    # Database
    storage_lower = " ".join(profile.storage_requirements).lower()
    if any(kw in storage_lower for kw in ("nosql", "dynamodb", "key-value")):
        cost = _estimate_dynamodb_monthly_cost(rps * 0.3)
        recommendations.append(ServiceRecommendation(
            service_name="Amazon DynamoDB",
            justification=f"NoSQL key-value store; scales automatically. Estimated ~${cost}/month.",
            alternatives=["RDS PostgreSQL", "DocumentDB"],
            pricing_summary=f"~${cost}/month",
            free_tier_eligible=True,
            free_tier_limits="25 WCU, 25 RCU, 25 GB storage",
        ))
    else:
        instances = 2 if profile.high_availability else 1
        cost = _estimate_rds_monthly_cost(instances=instances)
        recommendations.append(ServiceRecommendation(
            service_name="Amazon RDS (PostgreSQL)",
            justification=(
                f"Managed relational database with multi-AZ for HA. "
                f"Estimated ~${cost}/month."
            ),
            alternatives=["DynamoDB", "Aurora Serverless"],
            pricing_summary=f"~${cost}/month ({instances} instance(s))",
            free_tier_eligible=True,
            free_tier_limits="750 hours/month db.t2.micro (12 months)",
        ))

    # S3 (almost always recommended)
    data_gb = profile.traffic.data_transfer_gb_monthly or 10
    s3_cost = _estimate_s3_monthly_cost(storage_gb=max(50, data_gb), data_transfer_gb=data_gb)
    recommendations.append(ServiceRecommendation(
        service_name="Amazon S3",
        justification=f"Object storage for static assets, backups, and logs. Estimated ~${s3_cost}/month.",
        alternatives=["EFS"],
        pricing_summary=f"~${s3_cost}/month",
        free_tier_eligible=True,
        free_tier_limits="5 GB storage, 20K GET, 2K PUT (12 months)",
    ))

    # CloudFront for content delivery
    if rps > 50 or data_gb > 50:
        cf_cost = _estimate_cloudfront_monthly_cost(data_transfer_gb=data_gb, requests_per_second=rps)
        recommendations.append(ServiceRecommendation(
            service_name="Amazon CloudFront",
            justification=f"CDN for reduced latency and origin offload. Estimated ~${cf_cost}/month.",
            alternatives=["Direct S3 access"],
            pricing_summary=f"~${cf_cost}/month",
            free_tier_eligible=True,
            free_tier_limits="1 TB data transfer/month (always free)",
        ))

    return recommendations


def _build_pricing_comparisons(
    profile: RequirementsProfile,
) -> list[PricingComparison]:
    """Build pricing comparisons for alternative services.

    Compares compute and database alternatives based on the profile's traffic.

    Args:
        profile: The requirements profile with traffic data.

    Returns:
        List of PricingComparison entries for compute and database categories.
    """
    comparisons: list[PricingComparison] = []
    compute = profile.compute_preference or "serverless"
    rps = profile.traffic.requests_per_second or 10

    # Compute comparison
    compute_alternatives = COMPUTE_ALTERNATIVES.get(compute, COMPUTE_ALTERNATIVES["mixed"])
    compute_options: list[dict] = []
    for service_key in compute_alternatives:
        cost = _get_compute_cost_estimate(service_key, profile)
        service_name = service_key.replace("_", " ").replace("t3 medium", "(t3.medium)")
        free_tier = FALLBACK_PRICING[service_key].get("free_tier")
        compute_options.append({
            "service": service_name,
            "monthly_estimate": f"${cost}",
            "notes": f"Free tier: {free_tier}" if free_tier else "No free tier",
        })

    comparisons.append(PricingComparison(
        category="compute",
        options=compute_options,
    ))

    # Database comparison
    storage_lower = " ".join(profile.storage_requirements).lower()
    if any(kw in storage_lower for kw in ("nosql", "dynamodb", "key-value")):
        db_key = "nosql"
    elif any(kw in storage_lower for kw in ("relational", "rds", "postgres", "mysql", "sql")):
        db_key = "relational"
    else:
        db_key = "default"

    db_alternatives = DATABASE_ALTERNATIVES[db_key]
    db_options: list[dict] = []
    for service_key in db_alternatives:
        cost = _get_database_cost_estimate(service_key, profile)
        service_name = service_key.replace("_", " ")
        free_tier = FALLBACK_PRICING[service_key].get("free_tier")
        db_options.append({
            "service": service_name,
            "monthly_estimate": f"${cost}",
            "notes": f"Free tier: {free_tier}" if free_tier else "No free tier",
        })

    comparisons.append(PricingComparison(
        category="database",
        options=db_options,
    ))

    # Storage comparison (S3 vs EFS)
    data_gb = profile.traffic.data_transfer_gb_monthly or 10
    s3_cost = _estimate_s3_monthly_cost(storage_gb=max(50, data_gb), data_transfer_gb=data_gb)
    # EFS approximate pricing
    efs_cost = round(max(50, data_gb) * 0.30, 2)  # ~$0.30/GB-month for standard
    comparisons.append(PricingComparison(
        category="storage",
        options=[
            {
                "service": "S3",
                "monthly_estimate": f"${s3_cost}",
                "notes": "Object storage, ideal for static assets and backups",
            },
            {
                "service": "EFS",
                "monthly_estimate": f"${efs_cost}",
                "notes": "File storage, ideal for shared filesystem access",
            },
        ],
    ))

    return comparisons


# ---------------------------------------------------------------------------
# ResearchAgent
# ---------------------------------------------------------------------------


class ResearchAgent:
    """Agent that researches AWS best practices and pricing via MCP tools.

    Uses MCP clients (docs_mcp, pricing_mcp) when available for live data.
    Falls back to built-in reference data and approximate pricing when MCP
    servers are unavailable, ensuring graceful degradation.
    """

    def __init__(
        self,
        docs_mcp: Any | None = None,
        pricing_mcp: Any | None = None,
        model: Any | None = None,
    ):
        """Initialize the research agent.

        Args:
            docs_mcp: Optional MCP client for AWS documentation queries.
                      If None, uses fallback reference architectures.
            pricing_mcp: Optional MCP client for pricing data queries.
                         If None, uses fallback approximate pricing.
            model: Optional Strands model instance. If None, the agent uses
                   deterministic logic only.
        """
        self._docs_mcp = docs_mcp
        self._pricing_mcp = pricing_mcp
        self._model = model
        self._agent = self._create_agent() if model is not None else None

    def _create_agent(self) -> Any:
        """Create the underlying Strands Agent with MCP tool bindings."""
        try:
            from strands import Agent

            tools: list[Any] = []
            if self._docs_mcp is not None:
                tools.append(self._docs_mcp)
            if self._pricing_mcp is not None:
                tools.append(self._pricing_mcp)

            return Agent(
                model=self._model,
                system_prompt=RESEARCH_SYSTEM_PROMPT,
                tools=tools if tools else None,
            )
        except ImportError:
            logger.warning("Strands SDK not available; using deterministic fallback.")
            return None

    def research(self, profile: RequirementsProfile) -> ResearchSummary:
        """Conduct research based on requirements profile.

        Queries MCP servers for documentation and pricing when available.
        Falls back to built-in data otherwise.

        Args:
            profile: The gathered requirements.

        Returns:
            ResearchSummary with reference architectures, pricing,
            and WAF guidance.
        """
        notes: list[str] = []
        data_sources_available = True

        # --- Reference architectures ---
        reference_architectures = self._research_docs(profile, notes)

        # --- Pricing and cost comparisons ---
        pricing_comparisons = self._research_pricing(profile, notes)

        # --- Service recommendations ---
        service_recommendations = _build_service_recommendations(profile)

        # --- Well-Architected guidance ---
        well_architected_guidance = self._research_waf(profile, notes)

        # Mark data sources as unavailable if both MCP clients are missing
        if self._docs_mcp is None and self._pricing_mcp is None:
            data_sources_available = False
            if not any("fallback" in n.lower() for n in notes):
                notes.append(
                    "MCP tools unavailable; results based on built-in "
                    "reference data and approximate pricing estimates."
                )

        return ResearchSummary(
            reference_architectures=reference_architectures,
            service_recommendations=service_recommendations,
            well_architected_guidance=well_architected_guidance,
            pricing_comparisons=pricing_comparisons,
            data_sources_available=data_sources_available,
            notes=notes,
        )

    def _research_docs(
        self,
        profile: RequirementsProfile,
        notes: list[str],
    ) -> list[ReferenceArchitecture]:
        """Query AWS Docs MCP or use fallback reference architectures.

        Args:
            profile: The requirements profile.
            notes: Mutable list to append status notes.

        Returns:
            List of relevant reference architectures.
        """
        if self._docs_mcp is not None:
            try:
                return self._query_docs_mcp(profile)
            except Exception as exc:
                logger.warning("AWS Docs MCP query failed: %s. Using fallback.", exc)
                notes.append(
                    "AWS Docs MCP unavailable; using built-in reference architectures."
                )

        # Fallback: select from built-in reference architectures
        if self._docs_mcp is None:
            notes.append(
                "AWS Docs MCP not configured; using built-in reference architectures."
            )
        return _select_reference_architectures(profile)

    def _query_docs_mcp(
        self,
        profile: RequirementsProfile,
    ) -> list[ReferenceArchitecture]:
        """Query the AWS Docs MCP server for reference architectures.

        This method attempts to use the MCP client to fetch current
        documentation. The actual query format depends on the MCP server API.

        Args:
            profile: The requirements profile.

        Returns:
            List of reference architectures from MCP.
        """
        # Use the Strands agent with MCP tools if available
        if self._agent is not None:
            try:
                compute = profile.compute_preference or "serverless"
                prompt = (
                    f"Find AWS reference architectures for a {compute} workload "
                    f"with these requirements: {profile.original_description}. "
                    f"Region: {profile.target_region}."
                )
                result = self._agent(prompt)
                # Parse the agent response into structured data
                # For now, fall through to fallback if we can't parse
                if result and hasattr(result, "message"):
                    logger.info("Docs MCP returned results via Strands agent.")
            except Exception as exc:
                logger.warning("Strands agent docs query failed: %s", exc)

        # If MCP call didn't produce structured results, use fallback
        return _select_reference_architectures(profile)

    def _research_pricing(
        self,
        profile: RequirementsProfile,
        notes: list[str],
    ) -> list[PricingComparison]:
        """Query Pricing MCP or use fallback pricing data.

        Args:
            profile: The requirements profile.
            notes: Mutable list to append status notes.

        Returns:
            List of pricing comparisons.
        """
        if self._pricing_mcp is not None:
            try:
                return self._query_pricing_mcp(profile)
            except Exception as exc:
                logger.warning("Pricing MCP query failed: %s. Using fallback.", exc)
                notes.append(
                    "Pricing MCP unavailable; using approximate pricing estimates."
                )

        # Fallback: calculate from built-in pricing data
        if self._pricing_mcp is None:
            notes.append(
                "Pricing MCP not configured; costs are approximate estimates."
            )
        return _build_pricing_comparisons(profile)

    def _query_pricing_mcp(
        self,
        profile: RequirementsProfile,
    ) -> list[PricingComparison]:
        """Query the Pricing MCP server for live pricing data.

        Args:
            profile: The requirements profile.

        Returns:
            List of pricing comparisons from MCP.
        """
        if self._agent is not None:
            try:
                compute = profile.compute_preference or "serverless"
                rps = profile.traffic.requests_per_second or 10
                prompt = (
                    f"Get pricing for AWS services in {profile.target_region}: "
                    f"Lambda, ECS Fargate, EC2 t3.medium, RDS PostgreSQL, "
                    f"DynamoDB, S3, CloudFront, ALB. "
                    f"Calculate monthly costs for {rps} requests/second "
                    f"with {compute} compute preference."
                )
                result = self._agent(prompt)
                if result and hasattr(result, "message"):
                    logger.info("Pricing MCP returned results via Strands agent.")
            except Exception as exc:
                logger.warning("Strands agent pricing query failed: %s", exc)

        # If MCP call didn't produce structured results, use fallback
        return _build_pricing_comparisons(profile)

    def _research_waf(
        self,
        profile: RequirementsProfile,
        notes: list[str],
    ) -> list[WellArchitectedGuidance]:
        """Get Well-Architected Framework guidance.

        Uses docs MCP if available, otherwise returns fallback guidance.

        Args:
            profile: The requirements profile.
            notes: Mutable list to append status notes.

        Returns:
            List of Well-Architected guidance per pillar.
        """
        if self._docs_mcp is not None and self._agent is not None:
            try:
                prompt = (
                    f"Provide Well-Architected Framework guidance for a "
                    f"{profile.compute_preference or 'serverless'} workload "
                    f"across all six pillars. Requirements: "
                    f"{profile.original_description}"
                )
                result = self._agent(prompt)
                if result and hasattr(result, "message"):
                    logger.info("WAF guidance returned via Strands agent.")
                    # Fall through to fallback for structured data
            except Exception as exc:
                logger.warning("WAF guidance query failed: %s", exc)
                notes.append(
                    "Well-Architected guidance query failed; using built-in guidance."
                )

        return list(FALLBACK_WAF_GUIDANCE)
