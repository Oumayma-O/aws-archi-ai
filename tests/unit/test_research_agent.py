"""Unit tests for the ResearchAgent module."""

import pytest

from agents.research import (
    ResearchAgent,
    _build_pricing_comparisons,
    _build_service_recommendations,
    _estimate_lambda_monthly_cost,
    _estimate_fargate_monthly_cost,
    _estimate_ec2_monthly_cost,
    _estimate_dynamodb_monthly_cost,
    _estimate_rds_monthly_cost,
    _estimate_s3_monthly_cost,
    _select_reference_architectures,
)
from models.requirements import RequirementsProfile, TrafficPattern


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def serverless_profile() -> RequirementsProfile:
    """A profile favouring serverless compute."""
    return RequirementsProfile(
        original_description="REST API for mobile app",
        compute_preference="serverless",
        traffic=TrafficPattern(
            requests_per_second=100,
            data_transfer_gb_monthly=30,
            peak_concurrent_users=2000,
        ),
        budget_monthly_usd=300,
        high_availability=True,
        storage_requirements=["RDS", "S3"],
        target_region="eu-west-1",
    )


@pytest.fixture
def container_profile() -> RequirementsProfile:
    """A profile favouring containers."""
    return RequirementsProfile(
        original_description="Microservices backend",
        compute_preference="containers",
        traffic=TrafficPattern(requests_per_second=500, data_transfer_gb_monthly=100),
        storage_requirements=["DynamoDB"],
        target_region="us-east-1",
    )


# ---------------------------------------------------------------------------
# ResearchAgent integration (no MCP, no model)
# ---------------------------------------------------------------------------


class TestResearchAgentFallback:
    """Test ResearchAgent with no MCP clients (graceful degradation)."""

    def test_research_returns_research_summary(self, serverless_profile):
        agent = ResearchAgent(docs_mcp=None, pricing_mcp=None, model=None)
        result = agent.research(serverless_profile)

        assert result is not None
        assert len(result.reference_architectures) > 0
        assert len(result.service_recommendations) > 0
        assert len(result.well_architected_guidance) == 6
        assert len(result.pricing_comparisons) >= 2
        assert result.data_sources_available is False

    def test_research_notes_mention_fallback(self, serverless_profile):
        agent = ResearchAgent(docs_mcp=None, pricing_mcp=None, model=None)
        result = agent.research(serverless_profile)

        assert len(result.notes) > 0
        combined_notes = " ".join(result.notes).lower()
        assert "mcp" in combined_notes or "fallback" in combined_notes or "not configured" in combined_notes

    def test_research_with_container_preference(self, container_profile):
        agent = ResearchAgent(docs_mcp=None, pricing_mcp=None, model=None)
        result = agent.research(container_profile)

        # Should recommend ECS Fargate as primary
        service_names = [s.service_name for s in result.service_recommendations]
        assert "ECS Fargate" in service_names

    def test_pricing_comparisons_cover_all_alternatives(self, serverless_profile):
        """Property 8: all candidate alternatives appear in pricing comparison."""
        agent = ResearchAgent(docs_mcp=None, pricing_mcp=None, model=None)
        result = agent.research(serverless_profile)

        compute_comp = next(c for c in result.pricing_comparisons if c.category == "compute")
        compute_services = [o["service"] for o in compute_comp.options]
        # For serverless profile, should include Lambda, ECS Fargate, EC2
        assert len(compute_services) == 3
        assert "Lambda" in compute_services

    def test_costs_nonzero_when_traffic_specified(self, serverless_profile):
        """Property 9: costs are non-zero when non-zero traffic is specified."""
        agent = ResearchAgent(docs_mcp=None, pricing_mcp=None, model=None)
        result = agent.research(serverless_profile)

        for comp in result.pricing_comparisons:
            for opt in comp.options:
                cost_str = opt["monthly_estimate"].replace("$", "")
                cost = float(cost_str)
                assert cost > 0, f"Zero cost for {opt['service']} in {comp.category}"


# ---------------------------------------------------------------------------
# Cost estimation helper tests
# ---------------------------------------------------------------------------


class TestCostEstimation:
    """Test individual cost estimation functions."""

    def test_lambda_cost_increases_with_rps(self):
        cost_low = _estimate_lambda_monthly_cost(10)
        cost_high = _estimate_lambda_monthly_cost(1000)
        assert cost_high > cost_low
        assert cost_low > 0

    def test_fargate_cost_scales_with_tasks(self):
        cost_2 = _estimate_fargate_monthly_cost(tasks=2)
        cost_4 = _estimate_fargate_monthly_cost(tasks=4)
        assert cost_4 > cost_2
        assert cost_2 > 0

    def test_ec2_cost_scales_with_instances(self):
        cost_2 = _estimate_ec2_monthly_cost(instances=2)
        cost_4 = _estimate_ec2_monthly_cost(instances=4)
        assert cost_4 == pytest.approx(cost_2 * 2, rel=0.01)

    def test_rds_cost_with_multi_az(self):
        cost_single = _estimate_rds_monthly_cost(instances=1)
        cost_multi = _estimate_rds_monthly_cost(instances=2)
        assert cost_multi > cost_single

    def test_dynamodb_cost_with_traffic(self):
        cost = _estimate_dynamodb_monthly_cost(requests_per_second=100, storage_gb=10)
        assert cost > 0

    def test_s3_cost_with_storage(self):
        cost = _estimate_s3_monthly_cost(storage_gb=100, data_transfer_gb=50)
        assert cost > 0


# ---------------------------------------------------------------------------
# Reference architecture selection
# ---------------------------------------------------------------------------


class TestReferenceArchitectures:
    """Test reference architecture selection logic."""

    def test_serverless_selects_serverless_refs(self, serverless_profile):
        refs = _select_reference_architectures(serverless_profile)
        names = [r.name for r in refs]
        assert "Serverless Web Application" in names

    def test_containers_selects_container_refs(self, container_profile):
        refs = _select_reference_architectures(container_profile)
        names = [r.name for r in refs]
        assert "Container-based Microservices on ECS" in names

    def test_analytics_storage_adds_data_lake(self):
        profile = RequirementsProfile(
            original_description="Analytics pipeline",
            compute_preference="serverless",
            storage_requirements=["S3", "Athena", "analytics"],
        )
        refs = _select_reference_architectures(profile)
        names = [r.name for r in refs]
        assert "Modern Data Lake" in names


# ---------------------------------------------------------------------------
# Service recommendations
# ---------------------------------------------------------------------------


class TestServiceRecommendations:
    """Test service recommendation generation."""

    def test_serverless_recommends_lambda(self, serverless_profile):
        recs = _build_service_recommendations(serverless_profile)
        names = [r.service_name for r in recs]
        assert "AWS Lambda" in names
        assert "Amazon API Gateway" in names

    def test_containers_recommends_fargate(self, container_profile):
        recs = _build_service_recommendations(container_profile)
        names = [r.service_name for r in recs]
        assert "ECS Fargate" in names
        assert "Application Load Balancer" in names

    def test_nosql_storage_recommends_dynamodb(self, container_profile):
        recs = _build_service_recommendations(container_profile)
        names = [r.service_name for r in recs]
        assert "Amazon DynamoDB" in names

    def test_relational_storage_recommends_rds(self, serverless_profile):
        recs = _build_service_recommendations(serverless_profile)
        names = [r.service_name for r in recs]
        assert "Amazon RDS (PostgreSQL)" in names


# ---------------------------------------------------------------------------
# MCP graceful degradation
# ---------------------------------------------------------------------------


class TestMCPDegradation:
    """Test that MCP unavailability is handled gracefully."""

    def test_none_mcp_clients_still_produces_results(self, serverless_profile):
        agent = ResearchAgent(docs_mcp=None, pricing_mcp=None, model=None)
        result = agent.research(serverless_profile)
        assert result.reference_architectures
        assert result.pricing_comparisons
        assert result.service_recommendations

    def test_failing_mcp_falls_back(self, serverless_profile):
        """Simulate a failing MCP client that raises on use."""

        class FailingMCP:
            pass

        agent = ResearchAgent(docs_mcp=FailingMCP(), pricing_mcp=FailingMCP(), model=None)
        result = agent.research(serverless_profile)
        # Should still produce results via fallback
        assert result.reference_architectures
        assert result.pricing_comparisons
