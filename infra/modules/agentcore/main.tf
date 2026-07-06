# Amazon Bedrock AgentCore Runtime hosting the architect agent workflow.
#
# Uses the awscc (Cloud Control) provider: the classic aws provider is
# pinned ~> 5.0 in this repo, which predates native bedrockagentcore
# resources. The runtime pulls the ARM64 image the CD pipeline pushes to
# ECR under the :agentcore-latest tag.

terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
    awscc = {
      source  = "hashicorp/awscc"
      version = ">= 1.58.0"
    }
  }
}

data "aws_caller_identity" "current" {}

# ---------------------------------------------------------------------------
# Execution role — assumed by the AgentCore service to run the container
# ---------------------------------------------------------------------------

resource "aws_iam_role" "runtime" {
  name = "${var.project_name}-agentcore-runtime"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "bedrock-agentcore.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
      }
    }]
  })

  tags = { Project = var.project_name }
}

resource "aws_iam_role_policy" "runtime" {
  name = "${var.project_name}-agentcore-runtime"
  role = aws_iam_role.runtime.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "PullAgentImage"
        Effect   = "Allow"
        Action   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]
        Resource = var.ecr_repository_arn
      },
      {
        Sid      = "EcrAuth"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid    = "InvokeBedrockModels"
        Effect = "Allow"
        Action = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
        Resource = "*"
      },
      {
        Sid    = "SessionStore"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query",
          "dynamodb:UpdateItem", "dynamodb:DescribeTable",
        ]
        Resource = [var.dynamodb_table_arn, "${var.dynamodb_table_arn}/index/*"]
      },
      {
        Sid    = "Logs"
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogGroups", "logs:DescribeLogStreams"]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/bedrock-agentcore/*"
      },
      {
        Sid      = "PriceListRead"
        Effect   = "Allow"
        Action   = ["pricing:GetProducts", "pricing:DescribeServices", "pricing:GetAttributeValues"]
        Resource = "*"
      },
      {
        Sid    = "Observability"
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments", "xray:PutTelemetryRecords",
          "cloudwatch:PutMetricData",
        ]
        Resource = "*"
      },
      {
        Sid      = "WorkloadIdentity"
        Effect   = "Allow"
        Action   = ["bedrock-agentcore:GetWorkloadAccessToken"]
        Resource = "*"
      },
    ]
  })
}

# ---------------------------------------------------------------------------
# The runtime itself
# ---------------------------------------------------------------------------

resource "awscc_bedrockagentcore_runtime" "architect" {
  agent_runtime_name = replace("${var.project_name}_agent", "-", "_")
  description        = "AWS Architect AI — orchestrated agent workflow (clarify/research/design/review/diagram)"
  role_arn           = aws_iam_role.runtime.arn

  agent_runtime_artifact = {
    container_configuration = {
      container_uri = "${var.ecr_repository_url}:${var.image_tag}"
    }
  }

  network_configuration = {
    network_mode = "PUBLIC"
  }

  protocol_configuration = "HTTP"

  environment_variables = {
    AWS_REGION          = var.aws_region
    BEDROCK_MODEL_ID    = var.bedrock_model_id
    SESSION_TABLE_NAME  = var.session_table_name
    RESEARCH_MAX_TURNS  = "6"
    MCP_DOCS_URL        = var.mcp_docs_url
    # Pricing server is pip-installed in the image (Dockerfile.agentcore);
    # its stdio console script is spawned per session.
    MCP_PRICING_COMMAND = var.mcp_pricing_command
    MCP_DRAWIO_URL      = var.mcp_drawio_url
  }
}
