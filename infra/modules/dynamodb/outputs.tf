output "table_name" {
  description = "Name of the architect-sessions DynamoDB table"
  value       = aws_dynamodb_table.architect_sessions.name
}

output "table_arn" {
  description = "ARN of the architect-sessions DynamoDB table"
  value       = aws_dynamodb_table.architect_sessions.arn
}
