variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository in format owner/repo (e.g., Oumayma-O/aws-archi-ai)"
  type        = string
}
