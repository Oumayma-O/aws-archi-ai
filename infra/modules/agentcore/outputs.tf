output "runtime_arn" {
  description = "Set this as AGENTCORE_RUNTIME_ARN in the Streamlit task env"
  value       = awscc_bedrockagentcore_runtime.architect.agent_runtime_arn
}

output "runtime_id" {
  value = awscc_bedrockagentcore_runtime.architect.agent_runtime_id
}

output "runtime_role_arn" {
  value = aws_iam_role.runtime.arn
}
