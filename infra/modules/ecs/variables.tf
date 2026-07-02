variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
}

variable "aws_region" {
  description = "AWS region for CloudWatch Logs configuration"
  type        = string
}

variable "bedrock_model_id" {
  description = "Amazon Bedrock model ID passed as environment variable to the container"
  type        = string
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

variable "ecr_repository_url" {
  description = "ECR repository URL for the container image"
  type        = string
}

variable "private_subnets" {
  description = "List of private subnet IDs for ECS task placement"
  type        = list(string)
}

variable "ecs_sg_id" {
  description = "Security group ID for ECS tasks"
  type        = string
}

variable "target_group_arn" {
  description = "ALB target group ARN for load balancer attachment"
  type        = string
}

variable "execution_role_arn" {
  description = "ARN of the ECS Task Execution Role"
  type        = string
}

variable "task_role_arn" {
  description = "ARN of the ECS Task Role"
  type        = string
}
