# CaseMind Terraform variables.
# Do NOT run `terraform apply` until Checkpoint 4 is approved (billable AWS resources).

variable "aws_region" {
  description = "AWS region for all CaseMind resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment label (e.g. hackathon-demo)"
  type        = string
  default     = "hackathon-demo"
}

variable "project_name" {
  description = "Project name used for resource naming/tagging"
  type        = string
  default     = "casemind"
}

variable "cases_bucket_name" {
  description = "S3 bucket name that receives new case objects and triggers the Lambda agent loop. Must be globally unique."
  type        = string
}

variable "bedrock_model_id" {
  description = "Bedrock model ID used for case reasoning (agent/reasoning.py)"
  type        = string
}

variable "cockroachdb_connection_string" {
  description = "CockroachDB connection string, injected as a Lambda env var. Sourced from .env at deploy time — never hardcoded here."
  type        = string
  sensitive   = true
}

variable "cockroachdb_mcp_url" {
  description = "CockroachDB Managed MCP Server URL"
  type        = string
  default     = "https://cockroachlabs.cloud/mcp"
}

variable "lambda_timeout_seconds" {
  description = "Timeout for the agent orchestration Lambda"
  type        = number
  default     = 60
}

variable "lambda_memory_mb" {
  description = "Memory allocated to the agent orchestration Lambda"
  type        = number
  default     = 512
}
