output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = module.alb.dns_name
}

output "ecr_repository_url" {
  description = "ECR repository URL for pushing images"
  value       = module.ecr.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.ecs.cluster_name
}

output "ecs_service_name" {
  description = "ECS service name"
  value       = module.ecs.service_name
}

output "agentcore_runtime_arn" {
  description = "Set as AGENTCORE_RUNTIME_ARN in the Streamlit environment to route agent execution through AgentCore"
  value       = var.enable_agentcore ? module.agentcore[0].runtime_arn : null
}
