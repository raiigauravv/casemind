# CaseMind Terraform root module.
# DO NOT RUN `terraform init` / `terraform apply` until Checkpoint 4 is
# approved by Gaurav — this provisions billable AWS resources.

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# S3 bucket that receives new flagged case objects and triggers the agent
# Lambda. Bucket name must be supplied via var.cases_bucket_name (globally
# unique) — set in terraform.tfvars, never hardcoded.
resource "aws_s3_bucket" "cases" {
  bucket = var.cases_bucket_name

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_s3_bucket_notification" "cases_trigger" {
  bucket = aws_s3_bucket.cases.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.agent_loop.arn
    events              = ["s3:ObjectCreated:*"]
  }

  depends_on = [aws_lambda_permission.allow_s3_invoke]
}
