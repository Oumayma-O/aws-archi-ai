output "repository_url" {
  description = "ECR repository URL for pushing Docker images"
  value       = aws_ecr_repository.app.repository_url
}

output "repository_arn" {
  description = "ECR repository ARN (used by the AgentCore runtime pull policy)"
  value       = aws_ecr_repository.app.arn
}
