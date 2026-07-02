"""Cost formatting service for preparing cost data for UI display."""

from models.architecture import CostSummary, EstimatedCost


def format_cost_summary(estimated_cost: EstimatedCost) -> CostSummary:
    """Format cost estimation data for UI display.

    Takes the raw cost estimation from the architecture model and formats it
    into a summary structure suitable for rendering in the Cost tab.

    Args:
        estimated_cost: Cost data from the architecture model containing
            total monthly cost and per-service breakdown.

    Returns:
        Formatted cost summary with total monthly cost and per-service list.
    """
    return CostSummary(
        total_monthly=estimated_cost.total_monthly,
        services=list(estimated_cost.breakdown),
    )
