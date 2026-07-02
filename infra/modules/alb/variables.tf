variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where the ALB target group will be created"
  type        = string
}

variable "public_subnets" {
  description = "List of public subnet IDs for ALB placement"
  type        = list(string)
}

variable "alb_sg_id" {
  description = "Security group ID for the ALB"
  type        = string
}

variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS listener (optional, empty string to skip)"
  type        = string
  default     = ""
}
