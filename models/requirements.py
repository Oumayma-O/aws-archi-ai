"""Data models for requirements gathering and profiling."""

from pydantic import BaseModel, Field


class TrafficPattern(BaseModel):
    """Expected traffic characteristics."""

    peak_concurrent_users: int | None = None
    requests_per_second: int | None = None
    data_transfer_gb_monthly: float | None = None
    pattern: str = Field(
        default="steady", description="steady, spiky, periodic, growing"
    )


class ComplianceRequirement(BaseModel):
    """Compliance and regulatory requirements."""

    frameworks: list[str] = Field(
        default_factory=list, description="e.g., HIPAA, SOC2, GDPR, PCI-DSS"
    )
    data_residency: str | None = None
    encryption_requirements: list[str] = Field(default_factory=list)


class RequirementsProfile(BaseModel):
    """Structured output of the clarification phase."""

    original_description: str
    compute_preference: str | None = Field(
        default=None,
        description="serverless, containers, instances, or mixed",
    )
    budget_monthly_usd: float | None = None
    compliance: ComplianceRequirement = Field(
        default_factory=ComplianceRequirement
    )
    multi_region: bool = False
    disaster_recovery: str | None = Field(
        default=None,
        description="pilot-light, warm-standby, active-active, or none",
    )
    traffic: TrafficPattern = Field(default_factory=TrafficPattern)
    storage_requirements: list[str] = Field(default_factory=list)
    authentication: str | None = Field(
        default=None, description="cognito, iam, third-party, none"
    )
    high_availability: bool = True
    additional_constraints: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(
        default_factory=list,
        description="Defaults assumed when user skipped clarification",
    )
    target_region: str = Field(default="eu-west-1")
    iac_preference: str | None = Field(
        default=None,
        description="terraform, cdk, cloudformation, or none",
    )
