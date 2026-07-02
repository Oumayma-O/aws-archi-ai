"""Unit tests for the response parser service."""

import json

import pytest
from pydantic import ValidationError

from models.architecture import ArchitectureModel
from services.exceptions import JsonExtractionError
from services.parser import extract_json, parse_architecture


class TestExtractJson:
    """Tests for extract_json function."""

    def test_extracts_json_from_plain_text(self) -> None:
        """Extract JSON when surrounded by plain text."""
        text = 'Here is the response: {"key": "value"} hope that helps!'
        result = extract_json(text)
        assert json.loads(result) == {"key": "value"}

    def test_extracts_json_with_nested_braces(self) -> None:
        """Extract JSON containing nested objects."""
        text = 'prefix {"a": {"b": 1}, "c": [{"d": 2}]} suffix'
        result = extract_json(text)
        assert json.loads(result) == {"a": {"b": 1}, "c": [{"d": 2}]}

    def test_extracts_outermost_json(self) -> None:
        """Extract the outermost JSON object when multiple exist."""
        text = '{"outer": {"inner": true}} {"second": false}'
        result = extract_json(text)
        assert json.loads(result) == {"outer": {"inner": True}}

    def test_handles_braces_inside_strings(self) -> None:
        """Braces inside string values are ignored."""
        text = '{"code": "if (x) { return }"}'
        result = extract_json(text)
        assert json.loads(result) == {"code": "if (x) { return }"}

    def test_handles_escaped_quotes_in_strings(self) -> None:
        """Escaped quotes inside strings don't break parsing."""
        text = '{"msg": "she said \\"hello\\""}'
        result = extract_json(text)
        assert json.loads(result)["msg"] == 'she said "hello"'

    def test_raises_error_when_no_braces(self) -> None:
        """Raise JsonExtractionError when no opening brace is found."""
        with pytest.raises(JsonExtractionError, match="no opening brace"):
            extract_json("no json here at all")

    def test_raises_error_when_unmatched_braces(self) -> None:
        """Raise JsonExtractionError when braces are unmatched."""
        with pytest.raises(JsonExtractionError, match="unmatched braces"):
            extract_json('{"incomplete": true')

    def test_extracts_json_with_no_surrounding_text(self) -> None:
        """Extract JSON when it is the entire input."""
        text = '{"simple": true}'
        result = extract_json(text)
        assert json.loads(result) == {"simple": True}


class TestParseArchitecture:
    """Tests for parse_architecture function."""

    @pytest.fixture
    def valid_architecture_json(self) -> str:
        """Return a valid architecture JSON string."""
        data = {
            "title": "Test Architecture",
            "summary": "A test summary",
            "architecture_description": "Detailed description of the architecture",
            "aws_services": [{"name": "EC2", "role": "Compute instances"}],
            "networking": {
                "vpc": "vpc-123",
                "subnets": ["subnet-a"],
                "security_groups": ["sg-1"],
                "load_balancers": [],
            },
            "security": {
                "iam_policies": ["AdminAccess"],
                "encryption": ["AES-256"],
                "cloudtrail": [],
                "waf_rules": [],
                "recommendations": ["Enable MFA"],
            },
            "scaling": {"strategy": "horizontal", "policies": ["cpu-target"]},
            "monitoring": {
                "cloudwatch_metrics": ["CPUUtilization"],
                "alarms": [],
                "dashboards": [],
            },
            "estimated_cost": {
                "total_monthly": "$150",
                "breakdown": [{"service": "EC2", "monthly_cost": "$100"}],
            },
            "diagram": {
                "nodes": [
                    {"id": "n1", "label": "Web Server", "aws_service": "EC2"}
                ],
                "connections": [],
            },
            "recommendations": ["Use auto-scaling groups"],
        }
        return json.dumps(data)

    def test_parses_valid_architecture(self, valid_architecture_json: str) -> None:
        """Parse valid JSON into ArchitectureModel."""
        result = parse_architecture(valid_architecture_json)
        assert isinstance(result, ArchitectureModel)
        assert result.title == "Test Architecture"
        assert len(result.aws_services) == 1
        assert result.aws_services[0].name == "EC2"

    def test_raises_validation_error_for_missing_fields(self) -> None:
        """Raise ValidationError when required fields are missing."""
        incomplete = json.dumps({"title": "Only Title"})
        with pytest.raises(ValidationError) as exc_info:
            parse_architecture(incomplete)
        errors = exc_info.value.errors()
        missing_fields = {tuple(e["loc"]) for e in errors if e["type"] == "missing"}
        assert ("summary",) in missing_fields
        assert ("architecture_description",) in missing_fields

    def test_raises_validation_error_for_wrong_types(self) -> None:
        """Raise ValidationError when field types are wrong."""
        bad_types = json.dumps(
            {
                "title": "Test",
                "summary": "Sum",
                "architecture_description": "Desc",
                "aws_services": "not a list",
                "networking": {},
                "security": {},
                "scaling": {},
                "monitoring": {},
                "estimated_cost": {"total_monthly": "$0", "breakdown": []},
                "diagram": {"nodes": [], "connections": []},
            }
        )
        with pytest.raises(ValidationError):
            parse_architecture(bad_types)

    def test_raises_json_decode_error_for_invalid_json(self) -> None:
        """Raise JSONDecodeError for malformed JSON strings."""
        with pytest.raises(json.JSONDecodeError):
            parse_architecture("not valid json {{}}")
