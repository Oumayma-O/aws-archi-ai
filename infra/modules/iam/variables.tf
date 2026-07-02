variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
}

variable "aws_region" {
  description = "AWS region for Bedrock model ARN construction"
  type        = string
}

variable "bedrock_model_id" {
  description = "Amazon Bedrock model identifier for IAM policy scoping"
  type        = string
}
