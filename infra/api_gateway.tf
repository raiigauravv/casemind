# CaseMind API Gateway — HTTP API front door for the Lambda agent loop.
#
# lambda_handler.py already accepts a direct-invocation payload shape
# ({"case_id", "entity_id", "narrative"}) for local testing (see its
# docstring) alongside the S3-event shape. This API Gateway HTTP API lets
# the Phase 7 frontend (built in Lovable) call that same handler
# synchronously over HTTPS, so the demo can show retrieval -> reasoning ->
# decision happen live in the browser instead of only via S3 upload.
#
# HTTP APIs (v2) are used instead of REST APIs (v1) for lower cost and
# simpler config — within the free tier for demo-scale traffic.

resource "aws_apigatewayv2_api" "cases_api" {
  name          = "${var.project_name}-cases-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"] # demo scope; tighten to the Lovable domain post-hackathon
    allow_methods = ["POST", "OPTIONS"]
    allow_headers = ["content-type"]
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_apigatewayv2_integration" "agent_loop_integration" {
  api_id                 = aws_apigatewayv2_api.cases_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.agent_loop.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "post_cases" {
  api_id    = aws_apigatewayv2_api.cases_api.id
  route_key = "POST /cases"
  target    = "integrations/${aws_apigatewayv2_integration.agent_loop_integration.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.cases_api.id
  name        = "$default"
  auto_deploy = true

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_lambda_permission" "allow_apigw_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.agent_loop.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.cases_api.execution_arn}/*/*"
}

output "cases_api_endpoint" {
  description = "POST here with {case_id, entity_id, narrative} to invoke the agent loop synchronously."
  value       = "${aws_apigatewayv2_api.cases_api.api_endpoint}/cases"
}
