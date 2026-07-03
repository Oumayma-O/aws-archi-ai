"""End-to-end integration tests: input → prompt → mocked response → parsed result → diagram."""

import json
from unittest.mock import MagicMock, patch
from xml.etree import ElementTree

import pytest

from models.architecture import ArchitectureModel, DiagramConnection, DiagramNode
from services.diagram import to_drawio_xml, to_mermaid
from services.parser import extract_json, parse_architecture
from services.prompt_builder import build_prompt


class TestEndToEndPipeline:
    """Test the full pipeline with mocked Bedrock: description → prompt → response → parse → diagrams."""

    @pytest.fixture
    def user_description(self) -> str:
        """A realistic user system description."""
        return (
            "I need a web application with a React frontend hosted on S3 with CloudFront, "
            "a REST API on Lambda behind API Gateway, a DynamoDB database for user data, "
            "and Cognito for authentication. The system should handle 10,000 concurrent users."
        )

    @pytest.fixture
    def mock_llm_architecture_json(self) -> str:
        """A valid architecture JSON that the mocked Bedrock would return."""
        architecture = {
            "title": "Serverless Web Application",
            "summary": "A scalable serverless web application using AWS managed services.",
            "architecture_description": (
                "This architecture leverages serverless services for a fully managed, "
                "auto-scaling web application. CloudFront serves static React assets from S3, "
                "API Gateway handles REST requests routed to Lambda functions, "
                "DynamoDB provides low-latency data storage, and Cognito manages user authentication."
            ),
            "aws_services": [
                {"name": "Amazon S3", "role": "Static website hosting for React frontend"},
                {"name": "Amazon CloudFront", "role": "CDN for global content delivery"},
                {"name": "Amazon API Gateway", "role": "REST API management and routing"},
                {"name": "AWS Lambda", "role": "Serverless compute for API logic"},
                {"name": "Amazon DynamoDB", "role": "NoSQL database for user data"},
                {"name": "Amazon Cognito", "role": "User authentication and authorization"},
            ],
            "networking": {
                "vpc": "Not required - serverless architecture uses AWS managed networking",
                "subnets": [],
                "security_groups": [],
                "load_balancers": [],
            },
            "security": {
                "iam_policies": [
                    "Lambda execution role with DynamoDB read/write",
                    "S3 bucket policy for CloudFront OAI",
                ],
                "encryption": [
                    "DynamoDB encryption at rest with AWS managed key",
                    "TLS 1.2 for all API communication",
                ],
                "cloudtrail": ["API Gateway access logging", "Lambda invocation tracking"],
                "waf_rules": ["Rate limiting on API Gateway"],
                "recommendations": ["Enable MFA on Cognito user pool"],
            },
            "scaling": {
                "strategy": "Fully serverless auto-scaling with no capacity management",
                "policies": [
                    "Lambda concurrent execution limit at 1000",
                    "DynamoDB on-demand capacity mode",
                ],
            },
            "monitoring": {
                "cloudwatch_metrics": ["Lambda Duration", "API Gateway 5xx Errors", "DynamoDB ThrottledRequests"],
                "alarms": ["Lambda error rate above 1%", "API Gateway latency above 3s"],
                "dashboards": ["Application performance dashboard"],
            },
            "estimated_cost": {
                "total_monthly": "$100-$250/month",
                "breakdown": [
                    {"service": "AWS Lambda", "monthly_cost": "$30-$80/month"},
                    {"service": "Amazon DynamoDB", "monthly_cost": "$25-$60/month"},
                    {"service": "Amazon CloudFront", "monthly_cost": "$20-$50/month"},
                    {"service": "Amazon API Gateway", "monthly_cost": "$15-$40/month"},
                    {"service": "Amazon S3", "monthly_cost": "$5-$10/month"},
                    {"service": "Amazon Cognito", "monthly_cost": "$5-$10/month"},
                ],
            },
            "diagram": {
                "nodes": [
                    {"id": "cloudfront", "label": "CloudFront CDN", "aws_service": "CloudFront"},
                    {"id": "s3", "label": "S3 Static Hosting", "aws_service": "S3"},
                    {"id": "apigw", "label": "API Gateway", "aws_service": "API Gateway"},
                    {"id": "lambda_fn", "label": "Lambda Functions", "aws_service": "Lambda"},
                    {"id": "dynamodb", "label": "DynamoDB", "aws_service": "DynamoDB"},
                    {"id": "cognito", "label": "Cognito Auth", "aws_service": "Cognito"},
                ],
                "connections": [
                    {"source_id": "cloudfront", "target_id": "s3", "label": "Static assets"},
                    {"source_id": "cloudfront", "target_id": "apigw", "label": "API requests"},
                    {"source_id": "apigw", "target_id": "lambda_fn", "label": "Route requests"},
                    {"source_id": "lambda_fn", "target_id": "dynamodb", "label": "Read/Write"},
                    {"source_id": "apigw", "target_id": "cognito", "label": "Auth"},
                ],
            },
            "recommendations": [
                "Use CloudFront Functions for simple request transformations",
                "Enable DynamoDB point-in-time recovery",
                "Implement API Gateway request validation",
            ],
        }
        return json.dumps(architecture)

    def test_full_pipeline_produces_valid_architecture(
        self, user_description: str, mock_llm_architecture_json: str
    ):
        """Full pipeline: build prompt → mock Bedrock response → parse → get valid ArchitectureModel."""
        # Step 1: Build the prompt (real)
        prompt = build_prompt(user_description)
        assert user_description in prompt

        # Step 2: Simulate Bedrock response (mock returns architecture JSON)
        response_text = mock_llm_architecture_json

        # Step 3: Extract JSON from response (real)
        extracted_json = extract_json(response_text)

        # Step 4: Parse into ArchitectureModel (real)
        architecture = parse_architecture(extracted_json)

        # Step 5: Verify ArchitectureModel fields
        assert isinstance(architecture, ArchitectureModel)
        assert architecture.title == "Serverless Web Application"
        assert len(architecture.aws_services) == 6
        assert architecture.estimated_cost.total_monthly == "$100-$250/month"
        assert len(architecture.diagram.nodes) == 6
        assert len(architecture.diagram.connections) == 5
        assert len(architecture.recommendations) == 3

    def test_full_pipeline_generates_mermaid_output(
        self, user_description: str, mock_llm_architecture_json: str
    ):
        """Full pipeline produces valid Mermaid diagram output."""
        # Parse the architecture
        extracted_json = extract_json(mock_llm_architecture_json)
        architecture = parse_architecture(extracted_json)

        # Generate Mermaid (real)
        mermaid_code = to_mermaid(
            architecture.diagram.nodes, architecture.diagram.connections
        )

        # Verify Mermaid output
        assert mermaid_code.startswith("flowchart TD")
        assert "cloudfront" in mermaid_code
        assert "s3" in mermaid_code
        assert "apigw" in mermaid_code
        assert "lambda_fn" in mermaid_code
        assert "dynamodb" in mermaid_code
        assert "cognito" in mermaid_code
        # Verify connections are present
        assert "-->" in mermaid_code

    def test_full_pipeline_generates_drawio_output(
        self, user_description: str, mock_llm_architecture_json: str
    ):
        """Full pipeline produces valid Draw.io XML output."""
        # Parse the architecture
        extracted_json = extract_json(mock_llm_architecture_json)
        architecture = parse_architecture(extracted_json)

        # Generate Draw.io XML (real)
        drawio_xml = to_drawio_xml(
            architecture.diagram.nodes, architecture.diagram.connections
        )

        # Verify Draw.io XML is well-formed
        assert drawio_xml.strip() != ""
        root = ElementTree.fromstring(drawio_xml)
        assert root.tag == "mxGraphModel"

        # Verify node cells exist (one per node)
        all_cells = root.findall(".//mxCell")
        # 2 default cells + 6 node cells + 5 edge cells = 13
        vertex_cells = [c for c in all_cells if c.get("vertex") == "1"]
        edge_cells = [c for c in all_cells if c.get("edge") == "1"]
        assert len(vertex_cells) == 6
        assert len(edge_cells) == 5

    @patch("services.bedrock.load_config")
    @patch("services.bedrock.get_bedrock_client")
    def test_full_pipeline_with_mocked_bedrock_client(
        self,
        mock_get_client,
        mock_load_config,
        user_description: str,
        mock_llm_architecture_json: str,
    ):
        """Full end-to-end test: input → prompt → mocked Bedrock → parse → diagrams."""
        from services.bedrock import invoke_model

        # Configure mocked config
        mock_config = MagicMock()
        mock_config.aws_region = "eu-west-1"
        mock_config.aws_profile = None
        mock_load_config.return_value = mock_config

        # Configure mocked Bedrock client (Converse API response format)
        mock_client = MagicMock()
        mock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": mock_llm_architecture_json}]
                }
            }
        }
        mock_get_client.return_value = mock_client

        # Step 1: Build prompt (real)
        prompt = build_prompt(user_description)

        # Step 2: Invoke model (mocked Bedrock)
        response_text = invoke_model(
            prompt=prompt,
            model_id="eu.anthropic.claude-haiku-4-5-20251001-v1:0",
            temperature=0.7,
        )

        # Step 3: Parse response (real)
        extracted_json = extract_json(response_text)
        architecture = parse_architecture(extracted_json)

        # Step 4: Generate diagrams (real)
        mermaid_code = to_mermaid(
            architecture.diagram.nodes, architecture.diagram.connections
        )
        drawio_xml = to_drawio_xml(
            architecture.diagram.nodes, architecture.diagram.connections
        )

        # Verify the full flow produced valid outputs
        assert isinstance(architecture, ArchitectureModel)
        assert architecture.title == "Serverless Web Application"
        assert len(architecture.aws_services) == 6

        # Mermaid output is valid
        assert mermaid_code.startswith("flowchart TD")
        assert "cloudfront" in mermaid_code

        # Draw.io XML is well-formed
        root = ElementTree.fromstring(drawio_xml)
        assert root.tag == "mxGraphModel"

    def test_pipeline_with_wrapped_json_response(
        self, user_description: str, mock_llm_architecture_json: str
    ):
        """Pipeline handles LLM response with text wrapping around the JSON."""
        # Simulate LLM prefixing/suffixing the JSON with extra text
        wrapped_response = (
            "Here is the architecture I generated for you:\n\n"
            + mock_llm_architecture_json
            + "\n\nI hope this helps with your design!"
        )

        # Extract and parse should still work
        extracted_json = extract_json(wrapped_response)
        architecture = parse_architecture(extracted_json)

        assert isinstance(architecture, ArchitectureModel)
        assert architecture.title == "Serverless Web Application"
        assert len(architecture.diagram.nodes) == 6
