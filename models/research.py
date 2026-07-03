"""Pydantic models for the research phase output."""

from pydantic import BaseModel, Field


class ReferenceArchitecture(BaseModel):
    """An AWS reference architecture relevant to the workload."""

    name: str
    description: str
    url: str | None = None
    relevance: str = Field(description="Why this reference applies")


class ServiceRecommendation(BaseModel):
    """A recommended AWS service with justification."""

    service_name: str
    justification: str
    alternatives: list[str] = Field(default_factory=list)
    pricing_summary: str | None = None
    free_tier_eligible: bool = False
    free_tier_limits: str | None = None


class WellArchitectedGuidance(BaseModel):
    """Well-Architected Framework guidance for a specific pillar."""

    pillar: str
    recommendations: list[str]
    risks: list[str] = Field(default_factory=list)


class PricingComparison(BaseModel):
    """Cost comparison between alternative service options."""

    category: str = Field(description="e.g., 'compute', 'database', 'storage'")
    options: list[dict] = Field(
        description="Each option: {service, monthly_estimate, notes}"
    )


class ResearchSummary(BaseModel):
    """Complete output of the research phase."""

    reference_architectures: list[ReferenceArchitecture] = Field(
        default_factory=list
    )
    service_recommendations: list[ServiceRecommendation] = Field(
        default_factory=list
    )
    well_architected_guidance: list[WellArchitectedGuidance] = Field(
        default_factory=list
    )
    pricing_comparisons: list[PricingComparison] = Field(default_factory=list)
    data_sources_available: bool = True
    notes: list[str] = Field(default_factory=list)
