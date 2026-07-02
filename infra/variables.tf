variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "aws-architect-ai"
}

variable "bedrock_model_id" {
  description = "Amazon Bedrock inference profile ID"
  type        = string
  default     = "eu.anthropic.claude-sonnet-4-5-20250929-v1:0"
}

variable "container_cpu" {
  description = "ECS task CPU units"
  type        = number
  default     = 512
}

variable "container_memory" {
  description = "ECS task memory in MB"
  type        = number
  default     = 1024
}

variable "log_level" {
  description = "Application log level"
  type        = string
  default     = "INFO"
}

variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS (optional)"
  type        = string
  default     = ""
}
