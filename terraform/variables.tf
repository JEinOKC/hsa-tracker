variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (e.g., production, development)"
  type        = string
  default     = "production"
}

variable "bucket_name_prefix" {
  description = "Prefix for the S3 bucket name (will be made unique)"
  type        = string
  default     = "hsa-tracker-receipts"
}

variable "enable_versioning" {
  description = "Enable versioning for S3 bucket"
  type        = bool
  default     = true
}

variable "lifecycle_transition_days" {
  description = "Days before transitioning objects to Glacier"
  type        = number
  default     = 365
}

variable "lifecycle_expiration_days" {
  description = "Days before expiring non-current versions (0 to disable)"
  type        = number
  default     = 0
}

variable "enable_kms_encryption" {
  description = "Use KMS for encryption instead of SSE-S3"
  type        = bool
  default     = false
}

variable "allowed_cors_origins" {
  description = "Origins allowed to make direct browser uploads to S3 (presigned PUT URLs)"
  type        = list(string)
  default     = ["http://localhost:3001", "http://localhost:3000"]
}
