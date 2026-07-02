"""Unit tests for the cost formatting service."""

from models.architecture import CostSummary, EstimatedCost, ServiceCost
from services.cost import format_cost_summary


def test_format_cost_summary_basic():
    """Test formatting a cost with multiple services."""
    estimated_cost = EstimatedCost(
        total_monthly="$150.00",
        breakdown=[
            ServiceCost(service="EC2", monthly_cost="$80.00"),
            ServiceCost(service="S3", monthly_cost="$20.00"),
            ServiceCost(service="RDS", monthly_cost="$50.00"),
        ],
    )

    result = format_cost_summary(estimated_cost)

    assert isinstance(result, CostSummary)
    assert result.total_monthly == "$150.00"
    assert len(result.services) == 3
    assert result.services[0].service == "EC2"
    assert result.services[0].monthly_cost == "$80.00"
    assert result.services[1].service == "S3"
    assert result.services[2].service == "RDS"


def test_format_cost_summary_empty_breakdown():
    """Test formatting when no per-service breakdown is provided."""
    estimated_cost = EstimatedCost(
        total_monthly="$0.00",
        breakdown=[],
    )

    result = format_cost_summary(estimated_cost)

    assert result.total_monthly == "$0.00"
    assert result.services == []


def test_format_cost_summary_single_service():
    """Test formatting with a single service in the breakdown."""
    estimated_cost = EstimatedCost(
        total_monthly="$45.00",
        breakdown=[
            ServiceCost(service="Lambda", monthly_cost="$45.00"),
        ],
    )

    result = format_cost_summary(estimated_cost)

    assert result.total_monthly == "$45.00"
    assert len(result.services) == 1
    assert result.services[0].service == "Lambda"
    assert result.services[0].monthly_cost == "$45.00"
