"""Unit tests for the diagram renderer service."""

import xml.etree.ElementTree as ET

import pytest

from models.architecture import DiagramConnection, DiagramNode
from services.diagram import parse_mermaid, to_drawio_xml, to_mermaid


class TestToMermaid:
    """Tests for to_mermaid function."""

    def test_empty_nodes_returns_empty_string(self) -> None:
        """Empty nodes list returns empty string without error."""
        result = to_mermaid([], [])
        assert result == ""

    def test_single_node_no_connections(self) -> None:
        """Single node produces flowchart with one node definition."""
        nodes = [DiagramNode(id="ec2", label="Web Server", aws_service="EC2")]
        result = to_mermaid(nodes, [])
        assert "flowchart TD" in result
        assert 'ec2["Web Server (EC2)"]' in result

    def test_nodes_with_connections(self) -> None:
        """Nodes and connections produce valid flowchart syntax."""
        nodes = [
            DiagramNode(id="a", label="Service A", aws_service="Lambda"),
            DiagramNode(id="b", label="Service B", aws_service="S3"),
        ]
        connections = [
            DiagramConnection(source_id="a", target_id="b", label="sends data")
        ]
        result = to_mermaid(nodes, connections)
        assert "flowchart TD" in result
        assert 'a["Service A (Lambda)"]' in result
        assert 'b["Service B (S3)"]' in result
        assert "a -->|sends data| b" in result

    def test_connection_without_label(self) -> None:
        """Connection without label uses simple arrow syntax."""
        nodes = [
            DiagramNode(id="x", label="X", aws_service="EC2"),
            DiagramNode(id="y", label="Y", aws_service="RDS"),
        ]
        connections = [
            DiagramConnection(source_id="x", target_id="y", label=None)
        ]
        result = to_mermaid(nodes, connections)
        assert "x --> y" in result

    def test_skips_connection_with_invalid_source(self, caplog: pytest.LogCaptureFixture) -> None:
        """Connection with non-existent source_id is skipped with warning."""
        nodes = [DiagramNode(id="a", label="A", aws_service="EC2")]
        connections = [
            DiagramConnection(source_id="missing", target_id="a", label=None)
        ]
        result = to_mermaid(nodes, connections)
        assert "missing" not in result
        assert "Skipping connection" in caplog.text

    def test_skips_connection_with_invalid_target(self, caplog: pytest.LogCaptureFixture) -> None:
        """Connection with non-existent target_id is skipped with warning."""
        nodes = [DiagramNode(id="a", label="A", aws_service="EC2")]
        connections = [
            DiagramConnection(source_id="a", target_id="gone", label=None)
        ]
        result = to_mermaid(nodes, connections)
        assert "gone" not in result
        assert "Skipping connection" in caplog.text


class TestToDrawioXml:
    """Tests for to_drawio_xml function."""

    def test_empty_nodes_returns_empty_string(self) -> None:
        """Empty nodes list returns empty string without error."""
        result = to_drawio_xml([], [])
        assert result == ""

    def test_single_node_produces_valid_xml(self) -> None:
        """Single node produces well-formed XML with mxGraphModel root."""
        nodes = [DiagramNode(id="s3", label="Bucket", aws_service="S3")]
        result = to_drawio_xml(nodes, [])
        root = ET.fromstring(result)
        assert root.tag == "mxGraphModel"

    def test_node_count_in_xml(self) -> None:
        """Each node produces one mxCell with vertex=1."""
        nodes = [
            DiagramNode(id="a", label="A", aws_service="Lambda"),
            DiagramNode(id="b", label="B", aws_service="S3"),
            DiagramNode(id="c", label="C", aws_service="RDS"),
        ]
        result = to_drawio_xml(nodes, [])
        root = ET.fromstring(result)
        vertex_cells = [
            c for c in root.iter("mxCell")
            if c.get("vertex") == "1"
            # exclude AWS Cloud / VPC container boxes
            and "shape=mxgraph.aws4.group;" not in (c.get("style") or "")
        ]
        assert len(vertex_cells) == 3

    def test_edge_count_in_xml(self) -> None:
        """Each valid connection produces one mxCell with edge=1."""
        nodes = [
            DiagramNode(id="a", label="A", aws_service="Lambda"),
            DiagramNode(id="b", label="B", aws_service="S3"),
        ]
        connections = [
            DiagramConnection(source_id="a", target_id="b", label="data")
        ]
        result = to_drawio_xml(nodes, connections)
        root = ET.fromstring(result)
        edge_cells = [c for c in root.iter("mxCell") if c.get("edge") == "1"]
        assert len(edge_cells) == 1
        assert edge_cells[0].get("source") == "a"
        assert edge_cells[0].get("target") == "b"
        assert edge_cells[0].get("value") == "data"

    def test_skips_invalid_connections(self, caplog: pytest.LogCaptureFixture) -> None:
        """Connections with non-existent node IDs are omitted from XML."""
        nodes = [DiagramNode(id="a", label="A", aws_service="EC2")]
        connections = [
            DiagramConnection(source_id="a", target_id="nope", label=None)
        ]
        result = to_drawio_xml(nodes, connections)
        root = ET.fromstring(result)
        edge_cells = [c for c in root.iter("mxCell") if c.get("edge") == "1"]
        assert len(edge_cells) == 0
        assert "Skipping connection" in caplog.text


class TestParseMermaid:
    """Tests for parse_mermaid function."""

    def test_empty_input_returns_empty_lists(self) -> None:
        """Empty string returns empty nodes and connections."""
        nodes, connections = parse_mermaid("")
        assert nodes == []
        assert connections == []

    def test_whitespace_input_returns_empty_lists(self) -> None:
        """Whitespace-only input returns empty nodes and connections."""
        nodes, connections = parse_mermaid("   \n  \t  ")
        assert nodes == []
        assert connections == []

    def test_parses_nodes(self) -> None:
        """Correctly parses node definitions from Mermaid code."""
        mermaid = 'flowchart TD\n    ec2["Web Server (EC2)"]'
        nodes, _ = parse_mermaid(mermaid)
        assert len(nodes) == 1
        assert nodes[0].id == "ec2"
        assert nodes[0].label == "Web Server"
        assert nodes[0].aws_service == "EC2"

    def test_parses_labeled_connection(self) -> None:
        """Correctly parses labeled connection statements."""
        mermaid = (
            'flowchart TD\n'
            '    a["A (Lambda)"]\n'
            '    b["B (S3)"]\n'
            '    a -->|sends| b'
        )
        _, connections = parse_mermaid(mermaid)
        assert len(connections) == 1
        assert connections[0].source_id == "a"
        assert connections[0].target_id == "b"
        assert connections[0].label == "sends"

    def test_parses_unlabeled_connection(self) -> None:
        """Correctly parses unlabeled connection statements."""
        mermaid = (
            'flowchart TD\n'
            '    a["A (Lambda)"]\n'
            '    b["B (S3)"]\n'
            '    a --> b'
        )
        _, connections = parse_mermaid(mermaid)
        assert len(connections) == 1
        assert connections[0].source_id == "a"
        assert connections[0].target_id == "b"
        assert connections[0].label is None

    def test_round_trip_preserves_structure(self) -> None:
        """to_mermaid → parse_mermaid preserves all node IDs, labels, and connections."""
        nodes = [
            DiagramNode(id="vpc", label="VPC", aws_service="VPC"),
            DiagramNode(id="ec2", label="Web Server", aws_service="EC2"),
            DiagramNode(id="rds", label="Database", aws_service="RDS"),
        ]
        connections = [
            DiagramConnection(source_id="vpc", target_id="ec2", label="contains"),
            DiagramConnection(source_id="ec2", target_id="rds", label=None),
        ]

        mermaid_code = to_mermaid(nodes, connections)
        parsed_nodes, parsed_conns = parse_mermaid(mermaid_code)

        assert len(parsed_nodes) == len(nodes)
        assert len(parsed_conns) == len(connections)

        for orig, parsed in zip(nodes, parsed_nodes):
            assert orig.id == parsed.id
            assert orig.label == parsed.label
            assert orig.aws_service == parsed.aws_service

        for orig, parsed in zip(connections, parsed_conns):
            assert orig.source_id == parsed.source_id
            assert orig.target_id == parsed.target_id
            assert orig.label == parsed.label
