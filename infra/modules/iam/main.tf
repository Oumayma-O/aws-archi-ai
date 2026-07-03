# --- ECS Task Execution Role ---
# Allows ECS to pull images from ECR and write to CloudWatch Logs

data "aws_iam_policy_document" "ecs_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_task_execution" {
  name               = "${var.project_name}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json

  tags = {
    Name    = "${var.project_name}-ecs-execution"
    Project = var.project_name
  }
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_policy" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# --- ECS Task Role ---
# Allows the running container to invoke Bedrock models

resource "aws_iam_role" "ecs_task" {
  name               = "${var.project_name}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json

  tags = {
    Name    = "${var.project_name}-ecs-task"
    Project = var.project_name
  }
}

data "aws_iam_policy_document" "bedrock_invoke" {
  statement {
    effect    = "Allow"
    actions   = ["bedrock:InvokeModel"]
    resources = ["arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_model_id}"]
  }
}

resource "aws_iam_policy" "bedrock_invoke" {
  name        = "${var.project_name}-bedrock-invoke"
  description = "Allow ECS task to invoke the configured Bedrock model"
  policy      = data.aws_iam_policy_document.bedrock_invoke.json

  tags = {
    Name    = "${var.project_name}-bedrock-invoke"
    Project = var.project_name
  }
}

resource "aws_iam_role_policy_attachment" "ecs_task_bedrock" {
  role       = aws_iam_role.ecs_task.name
  policy_arn = aws_iam_policy.bedrock_invoke.arn
}

# --- DynamoDB Access for Session Persistence ---

data "aws_iam_policy_document" "dynamodb_sessions" {
  count = var.dynamodb_table_arn != "" ? 1 : 0

  statement {
    effect = "Allow"
    actions = [
      "dynamodb:PutItem",
      "dynamodb:GetItem",
      "dynamodb:Query",
      "dynamodb:DeleteItem",
    ]
    resources = [
      var.dynamodb_table_arn,
      "${var.dynamodb_table_arn}/index/*",
    ]
  }
}

resource "aws_iam_policy" "dynamodb_sessions" {
  count = var.dynamodb_table_arn != "" ? 1 : 0

  name        = "${var.project_name}-dynamodb-sessions"
  description = "Allow ECS task to access the architect-sessions DynamoDB table"
  policy      = data.aws_iam_policy_document.dynamodb_sessions[0].json

  tags = {
    Name    = "${var.project_name}-dynamodb-sessions"
    Project = var.project_name
  }
}

resource "aws_iam_role_policy_attachment" "ecs_task_dynamodb" {
  count = var.dynamodb_table_arn != "" ? 1 : 0

  role       = aws_iam_role.ecs_task.name
  policy_arn = aws_iam_policy.dynamodb_sessions[0].arn
}
