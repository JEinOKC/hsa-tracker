output "s3_bucket_name" {
  description = "Name of the S3 bucket for receipts"
  value       = aws_s3_bucket.receipts.id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = aws_s3_bucket.receipts.arn
}

output "s3_bucket_region" {
  description = "Region of the S3 bucket"
  value       = aws_s3_bucket.receipts.region
}

output "iam_user_name" {
  description = "Name of the IAM user for application access"
  value       = aws_iam_user.hsa_tracker_app.name
}

output "aws_access_key_id" {
  description = "AWS Access Key ID for the application (add to .env file)"
  value       = aws_iam_access_key.hsa_tracker_app.id
}

output "aws_secret_access_key" {
  description = "AWS Secret Access Key for the application (add to .env file)"
  value       = aws_iam_access_key.hsa_tracker_app.secret
  sensitive   = true
}

output "kms_key_id" {
  description = "KMS key ID for encryption (if enabled)"
  value       = var.enable_kms_encryption ? aws_kms_key.receipts[0].id : null
}

output "api_gateway_url" {
  description = "Base URL for the deployed API (set as VITE_API_URL in the frontend)"
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "ecr_repository_url" {
  description = "ECR repository URL — push your Lambda image here before deploying"
  value       = aws_ecr_repository.backend.repository_url
}

output "lambda_function_name" {
  description = "Lambda function name (useful for manual invocations and log tailing)"
  value       = aws_lambda_function.backend.function_name
}

output "api_url" {
  description = "API base URL — custom domain if configured, otherwise raw API Gateway URL"
  value       = var.api_custom_domain != "" ? "https://${var.api_custom_domain}" : aws_apigatewayv2_stage.default.invoke_url
}

output "frontend_pages_url" {
  description = "Cloudflare Pages deployment URL (available when cloudflare_enabled = true)"
  value       = var.cloudflare_enabled ? cloudflare_pages_project.frontend[0].subdomain : "N/A — cloudflare_enabled is false"
}

# Helpful commands to copy credentials to .env
output "env_file_instructions" {
  description = "Instructions for updating .env file"
  value       = <<-EOT

    ====================================================================
    TERRAFORM SETUP COMPLETE!
    ====================================================================

    Add these values to your .env file:

    AWS_S3_BUCKET=${aws_s3_bucket.receipts.id}
    AWS_S3_REGION=${aws_s3_bucket.receipts.region}
    AWS_ACCESS_KEY_ID=${aws_iam_access_key.hsa_tracker_app.id}
    AWS_SECRET_ACCESS_KEY=${nonsensitive(aws_iam_access_key.hsa_tracker_app.secret)}

    ====================================================================

    IMPORTANT: Save these credentials securely!
    The secret access key cannot be retrieved again.

    To view the secret access key again, run:
    terraform output aws_secret_access_key

    ====================================================================
  EOT
}
