"""Pydantic models for the comprehensive architecture report (Architect Mode output)."""

from pydantic import BaseModel, Field

from models.architecture import (
    DiagramData,
    EstimatedCost,
    MonitoringConfig,
    NetworkingConfig,
    ScalingConfig,
    SecurityConfig,
    ServiceDetail,
)


class VPCDesign(BaseModel):
    """Complete VPC topology design."""

    cidr_block: str
    public_subnets: list[dict] = Field(description="[{az, cidr, purpose}]")
    private_subnets: list[dict] = Field(description="[{az, cidr, purpose}]")
    nat_gateways: list[str] = Field(default_factory=list)
    internet_gateway: bool = True
    vpc_endpoints: list[dict] = Field(
        default_factory=list, description="[{service, type}]"
    )
    route_tables: list[dict] = Field(default_factory=list)
    security_groups: list[dict] = Field(
        default_factory=list, description="[{name, rules}]"
    )
    network_acls: list[dict] = Field(default_factory=list)
    validation_notes: list[str] = Field(default_factory=list)


class CostComparison(BaseModel):
    """Comparison between architectural alternatives."""

    approach_a: str
    approach_a_monthly: str
    approach_b: str
    approach_b_monthly: str
    recommendation: str
    reasoning: str


class ArchitectureRationale(BaseModel):
    """Rationale for a major design decision."""

    decision: str
    chosen_option: str
    alternatives_considered: list[str]
    reasoning: str


class WellArchitectedReview(BaseModel):
    """Review against all six Well-Architected pillars."""

    operational_excellence: list[str] = Field(default_factory=list)
    security: list[str] = Field(default_factory=list)
    reliability: list[str] = Field(default_factory=list)
    performance_efficiency: list[str] = Field(default_factory=list)
    cost_optimization: list[str] = Field(default_factory=list)
    sustainability: list[str] = Field(default_factory=list)
    violations: list[str] = Field(default_factory=list)
    improvement_opportunities: list[str] = Field(default_factory=list)


class ArchitectureReport(BaseModel):
    """Final comprehensive architecture report - Architect Mode output."""

    title: str
    summary: str
    architecture_description: str
    aws_services: list[ServiceDetail]
    networking: NetworkingConfig
    vpc_design: VPCDesign | None = None
    security: SecurityConfig
    scaling: ScalingConfig
    monitoring: MonitoringConfig
    estimated_cost: EstimatedCost
    cost_comparisons: list[CostComparison] = Field(default_factory=list)
    diagram: DiagramData
    recommendations: list[str] = Field(default_factory=list)
    rationale: list[ArchitectureRationale] = Field(default_factory=list)
    well_architected_review: WellArchitectedReview | None = None
    iac_skeleton: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    data_sources_used: list[str] = Field(default_factory=list)
