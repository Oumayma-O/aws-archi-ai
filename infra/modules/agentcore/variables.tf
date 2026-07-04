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
