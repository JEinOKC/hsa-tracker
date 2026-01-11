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
