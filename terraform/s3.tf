# Random suffix for unique bucket name
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

# S3 bucket for receipt storage
resource "aws_s3_bucket" "receipts" {
  bucket = "${var.bucket_name_prefix}-${random_id.bucket_suffix.hex}"

  tags = {
    Name = "HSA Tracker Receipts"
  }
}

# Block all public access
resource "aws_s3_bucket_public_access_block" "receipts" {
  bucket = aws_s3_bucket.receipts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Versioning configuration
resource "aws_s3_bucket_versioning" "receipts" {
  bucket = aws_s3_bucket.receipts.id

  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Disabled"
  }
}

# Server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "receipts" {
  bucket = aws_s3_bucket.receipts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = var.enable_kms_encryption ? "aws:kms" : "AES256"
      kms_master_key_id = var.enable_kms_encryption ? aws_kms_key.receipts[0].arn : null
    }
    bucket_key_enabled = var.enable_kms_encryption
  }
}

# Optional KMS key for encryption
resource "aws_kms_key" "receipts" {
  count = var.enable_kms_encryption ? 1 : 0

  description             = "KMS key for HSA Tracker receipt encryption"
  deletion_window_in_days = 10
  enable_key_rotation     = true

  tags = {
    Name = "HSA Tracker Receipts Encryption Key"
  }
}

resource "aws_kms_alias" "receipts" {
  count = var.enable_kms_encryption ? 1 : 0

  name          = "alias/hsa-tracker-receipts"
  target_key_id = aws_kms_key.receipts[0].key_id
}

# CORS configuration for direct uploads from browser
resource "aws_s3_bucket_cors_configuration" "receipts" {
  bucket = aws_s3_bucket.receipts.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "POST", "DELETE"]
    allowed_origins = ["http://localhost:3000", "http://localhost:80"] # Update with your domain
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# Lifecycle policy for cost optimization
resource "aws_s3_bucket_lifecycle_configuration" "receipts" {
  bucket = aws_s3_bucket.receipts.id

  rule {
    id     = "transition-old-receipts"
    status = "Enabled"

    transition {
      days          = var.lifecycle_transition_days
      storage_class = "GLACIER_IR"
    }

    # Only expire non-current versions if enabled
    dynamic "noncurrent_version_expiration" {
      for_each = var.lifecycle_expiration_days > 0 ? [1] : []
      content {
        noncurrent_days = var.lifecycle_expiration_days
      }
    }
  }
}
