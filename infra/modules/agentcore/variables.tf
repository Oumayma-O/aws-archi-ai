variable "project_name" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "bedrock_model_id" {
  type = string
}

variable "ecr_repository_url" {
  type = string
}

variable "ecr_repository_arn" {
  type = string
}

variable "dynamodb_table_arn" {
  type = string
}

variable "session_table_name" {
  type    = string
  default = "architect-sessions"
}

variable "image_tag" {
  description = "ECR tag of the ARM64 AgentCore payload image"
  type        = string
  default     = "agentcore-latest"
}

variable "mcp_docs_url" {
  description = "AWS Knowledge MCP endpoint (empty disables live research)"
  type        = string
  default     = "https://knowledge-mcp.global.api.aws"
}

variable "mcp_pricing_command" {
  description = "stdio command for the AWS Pricing MCP server (baked into the image; empty disables)"
  type        = string
  default     = "awslabs.aws-pricing-mcp-server"
}

variable "mcp_drawio_url" {
  description = "draw.io MCP endpoint (empty disables)"
  type        = string
  default     = "https://mcp.draw.io/mcp"
}
