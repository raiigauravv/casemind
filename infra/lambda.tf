# CaseMind Lambda + IAM resources.
# DO NOT RUN `terraform init` / `terraform apply` until Checkpoint 4 is
# approved by Gaurav — this provisions billable AWS resources.
#
# NOTE: whether AEGIS's existing IAM role/Terraform can be reused directly
# is an open question (see README "Open questions"). This module assumes a
# fresh, narrowly-scoped role until that's confirmed.

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "agent_lambda_role" {
  name               = "${var.project_name}-agent-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.agent_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "agent_permissions" {
  statement {
    sid     = "BedrockInvoke"
    actions = ["bedrock:InvokeModel"]
    resources = ["*"] # narrow to the specific model ARN once bedrock_model_id is finalized
  }

  statement {
    sid     = "ReadCasesBucket"
    actions = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.cases.arn}/*"]
  }
}

resource "aws_iam_role_policy" "agent_permissions" {
  name   = "${var.project_name}-agent-permissions"
  role   = aws_iam_role.agent_lambda_role.id
  policy = data.aws_iam_policy_document.agent_permissions.json
}

resource "aws_lambda_function" "agent_loop" {
  function_name = "${var.project_name}-agent-loop"
  role          = aws_iam_role.agent_lambda_role.arn
  handler       = "agent.lambda_handler.handler"
  runtime       = "python3.12"
  timeout       = var.lambda_timeout_seconds
  memory_size   = var.lambda_memory_mb

  # Placeholder deployment package — actual build/packaging step lands in
  # Phase 3 alongside the real lambda_handler.py implementation.
  filename         = "placeholder.zip"
  source_code_hash = filebase64sha256("placeholder.zip")

  environment {
    variables = {
      COCKROACHDB_CONNECTION_STRING = var.cockroachdb_connection_string
      COCKROACHDB_MCP_URL           = var.cockroachdb_mcp_url
      BEDROCK_MODEL_ID              = var.bedrock_model_id
      AWS_REGION                    = var.aws_region
    }
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_lambda_permission" "allow_s3_invoke" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.agent_loop.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.cases.arn
}
