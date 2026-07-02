"""Pydantic models for AWS architecture data structures."""

from pydantic import BaseModel, Field


class DiagramNode(BaseModel):
    """A single node in the architecture diagram."""

    id: str = Field(description="Unique node identifier")
    label: str = Field(description="Display label for the node")
    aws_service: str = Field(
        description="AWS service type (e.g., 'EC2', 'S3', 'Lambda')"
    )


class DiagramConnection(BaseModel):
    """A connection between two diagram nodes."""

    source_id: str = Field(description="ID of the source node")
    target_id: str = Field(description="ID of the target node")
    label: str | None = Field(default=None, description="Optional connection label")


class ServiceDetail(BaseModel):
    """Details for a single AWS service in the architecture."""

    name: str = Field(description="AWS service name")
    role: str = Field(description="Role/purpose in the architecture")


class SecurityConfig(BaseModel):
    """Security configuration details."""

    iam_policies: list[str] = Field(default_factory=list)
    encryption: list[str] = Field(default_factory=list)
    cloudtrail: list[str] = Field(default_factory=list)
    waf_rules: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class ServiceCost(BaseModel):
    """Cost estimate for a single service."""

    service: str = Field(description="AWS service name")
    monthly_cost: str = Field(description="Estimated monthly cost string")


class EstimatedCost(BaseModel):
    """Total cost estimation with per-service breakdown."""

    total_monthly: str = Field(description="Total estimated monthly cost")
    breakdown: list[ServiceCost] = Field(default_factory=list)


class NetworkingConfig(BaseModel):
    """Networking configuration details."""

    vpc: str = Field(default="")
    subnets: list[str] = Field(default_factory=list)
    security_groups: list[str] = Field(default_factory=list)
    load_balancers: list[str] = Field(default_factory=list)


class ScalingConfig(BaseModel):
    """Auto-scaling configuration details."""

    strategy: str = Field(default="")
    policies: list[str] = Field(default_factory=list)


class MonitoringConfig(BaseModel):
    """Monitoring and observability configuration."""

    cloudwatch_metrics: list[str] = Field(default_factory=list)
    alarms: list[str] = Field(default_factory=list)
    dashboards: list[str] = Field(default_factory=list)


class DiagramData(BaseModel):
    """Structured diagram representation with nodes and connections."""

    nodes: list[DiagramNode] = Field(default_factory=list)
    connections: list[DiagramConnection] = Field(default_factory=list)


class ArchitectureModel(BaseModel):
    """Complete architecture response from the LLM."""

    title: str = Field(description="Architecture title")
    summary: str = Field(description="Brief architecture summary")
    architecture_description: str = Field(
        description="Detailed architecture description"
    )
    aws_services: list[ServiceDetail] = Field(
        description="List of AWS services used"
    )
    networking: NetworkingConfig = Field(description="Networking configuration")
    security: SecurityConfig = Field(description="Security configuration")
    scaling: ScalingConfig = Field(description="Scaling configuration")
    monitoring: MonitoringConfig = Field(description="Monitoring configuration")
    estimated_cost: EstimatedCost = Field(description="Cost estimation")
    diagram: DiagramData = Field(
        description="Structured diagram nodes and connections"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Architecture recommendations"
    )


class CostSummary(BaseModel):
    """Formatted cost data for UI display."""

    total_monthly: str
    services: list[ServiceCost]
