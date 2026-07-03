"""Unit tests for the DiagramAgent class."""

import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

import pytest

from agents.diagram import DiagramAgent, DiagramResult
from models.architecture import (
    DiagramConnection,
    DiagramData,
    DiagramNode,
    EstimatedCost,
    MonitoringConfig,
    NetworkingConfig,
    ScalingConfig,
    SecurityConfig,
    ServiceDetail,
)
from models.report import ArchitectureReport


@pytest.fixture
def minimal_report() -> ArchitectureReport:
    """A minimal ArchitectureReport for diagram testing."""
    return ArchitectureReport(
        title="Test Architecture",
        summary="A test architecture",
        architecture_description="Test desc",
        aws_services=[ServiceDetail(name="Lambda", role="Compute")],
        networking=NetworkingConfig(),
        security=SecurityConfig(),
        scaling=ScalingConfig(),
        monitoring=MonitoringConfig(),
        estimated_cost=EstimatedCost(total_monthly="$100"),
        diagram=DiagramData(
            nodes=[DiagramNode(id="lambda1", label="API Handler", aws_service="Lambda")],
            connections=[],
        ),
    )


@pytest.fixture
def multi_node_report() -> ArchitectureReport:
    """A report with multiple nodes and connections."""
    return ArchitectureReport(
        title="Multi-tier Web App",
        summary="A multi-tier web application",
        architecture_description="Standard 3-tier",
        aws_services=[
            ServiceDetail(name="ALB", role="Load Balancer"),
            ServiceDetail(name="ECS", role="Compute"),
            ServiceDetail(name="RDS", role="Database"),
        ],
        networking=NetworkingConfig(vpc="vpc-123"),
        security=SecurityConfig(recommendations=["Use IAM"]),
        scaling=ScalingConfig(strategy="auto"),
        monitoring=MonitoringConfig(),
        estimated_cost=EstimatedCost(total_monthly="$500"),
        diagram=DiagramData(
            nodes=[
                DiagramNode(id="alb1", label="Load Balancer", aws_service="ALB"),
                DiagramNode(id="ecs1", label="ECS Cluster", aws_service="ECS"),
                DiagramNode(id="rds1", label="PostgreSQL", aws_service="RDS"),
            ],
            connections=[
                DiagramConnection(source_id="alb1", target_id="ecs1", label="HTTP"),
                DiagramConnection(source_id="ecs1", target_id="rds1", label="SQL"),
            ],
        ),
    )


class TestDiagramResult:
    """Tests for the DiagramResult model."""

    def test_create_with_xml_only(self):
        result = DiagramResult(drawio_xml="<mxGraphModel/>")
        assert result.drawio_xml == "<mxGraphModel/>"
        assert result.png_bytes is None

    def test_create_with_xml_and_png(self):
        result = DiagramResult(drawio_xml="<mxGraphModel/>", png_bytes=b"\x89PNG")
        assert result.drawio_xml == "<mxGraphModel/>"
        assert result.png_bytes == b"\x89PNG"


class TestDiagramAgentInit:
    """Tests for DiagramAgent initialization."""

    def test_default_init(self):
        agent = DiagramAgent()
        assert agent.drawio_mcp is None
        assert agent.model is None

    def test_init_with_mcp(self):
        mock_mcp = MagicMock()
        agent = DiagramAgent(drawio_mcp=mock_mcp)
        assert agent.drawio_mcp is mock_mcp
        assert agent.model is None

    def test_init_with_model(self):
        agent = DiagramAgent(model="us.anthropic.claude-sonnet-4-20250514")
        assert agent.model == "us.anthropic.claude-sonnet-4-20250514"

    def test_init_with_both(self):
        mock_mcp = MagicMock()
        agent = DiagramAgent(drawio_mcp=mock_mcp, model="test-model")
        assert agent.drawio_mcp is mock_mcp
        assert agent.model == "test-model"


class TestDiagramAgentLocalFallback:
    """Tests for DiagramAgent local fallback generation."""

    def test_generates_xml_without_mcp(self, minimal_report):
        agent = DiagramAgent(drawio_mcp=None)
        result = agent.generate(minimal_report)

        assert isinstance(result, DiagramResult)
        assert result.drawio_xml
        assert "<mxGraphModel" in result.drawio_xml

    def test_xml_is_well_formed(self, minimal_report):
        agent = DiagramAgent()
        result = agent.generate(minimal_report)

        # Should parse without error
        root = ET.fromstring(result.drawio_xml)
        assert root.tag == "mxGraphModel"

    def test_xml_contains_nodes(self, multi_node_report):
        agent = DiagramAgent()
        result = agent.generate(multi_node_report)

        root = ET.fromstring(result.drawio_xml)
        cells = root.findall(".//mxCell[@vertex='1']")
        # Should have 3 node cells
        assert len(cells) == 3

    def test_xml_contains_edges(self, multi_node_report):
        agent = DiagramAgent()
        result = agent.generate(multi_node_report)

        root = ET.fromstring(result.drawio_xml)
        edges = root.findall(".//mxCell[@edge='1']")
        # Should have 2 edge cells
        assert len(edges) == 2

    def test_empty_nodes_produces_empty_xml(self):
        report = ArchitectureReport(
            title="Empty",
            summary="Empty",
            architecture_description="Empty",
            aws_services=[],
            networking=NetworkingConfig(),
            security=SecurityConfig(),
            scaling=ScalingConfig(),
            monitoring=MonitoringConfig(),
            estimated_cost=EstimatedCost(total_monthly="$0"),
            diagram=DiagramData(nodes=[], connections=[]),
        )
        agent = DiagramAgent()
        result = agent.generate(report)

        assert result.drawio_xml == ""
        assert result.png_bytes is None


class TestDiagramAgentMCPFallback:
    """Tests for DiagramAgent MCP failure fallback behavior."""

    def test_falls_back_when_mcp_raises(self, minimal_report):
        """When MCP client causes an exception, agent falls back to local."""
        mock_mcp = MagicMock()
        agent = DiagramAgent(drawio_mcp=mock_mcp)

        # Patch _generate_via_mcp to simulate failure
        with patch.object(agent, "_generate_via_mcp", side_effect=RuntimeError("MCP failed")):
            result = agent.generate(minimal_report)

        assert isinstance(result, DiagramResult)
        assert "<mxGraphModel" in result.drawio_xml

    def test_falls_back_when_mcp_returns_none(self, minimal_report):
        """When MCP generation returns None, agent falls back to local."""
        mock_mcp = MagicMock()
        agent = DiagramAgent(drawio_mcp=mock_mcp)

        with patch.object(agent, "_generate_via_mcp", return_value=None):
            result = agent.generate(minimal_report)

        assert isinstance(result, DiagramResult)
        assert "<mxGraphModel" in result.drawio_xml
