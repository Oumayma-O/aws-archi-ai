# --- DynamoDB Table for Architect Sessions ---

resource "aws_dynamodb_table" "architect_sessions" {
  name         = "architect-sessions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"

  attribute {
    name = "session_id"
    type = "S"
  }

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "updated_at"
    type = "S"
  }

  global_secondary_index {
    name            = "user-sessions-index"
    hash_key        = "user_id"
    range_key       = "updated_at"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = {
    Name    = "architect-sessions"
    Project = var.project_name
  }
}
