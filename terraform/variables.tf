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

# ── Lambda / API Gateway variables ────────────────────────────────────────────

variable "lambda_image_tag" {
  description = "ECR image tag to deploy to Lambda (e.g. 'latest' or a git SHA)"
  type        = string
  default     = "latest"
}

variable "database_url" {
  description = "Neon (or other PostgreSQL) connection URL — use the pooled endpoint"
  type        = string
  sensitive   = true
}

variable "secret_key" {
  description = "Application secret key"
  type        = string
  sensitive   = true
}

variable "jwt_secret_key" {
  description = "Secret key used to sign JWT tokens"
  type        = string
  sensitive   = true
}

variable "jwt_access_token_expire_minutes" {
  description = "JWT access token lifetime in minutes"
  type        = number
  default     = 30
}

variable "jwt_refresh_token_expire_days" {
  description = "JWT refresh token lifetime in days"
  type        = number
  default     = 7
}

variable "webauthn_rp_id" {
  description = "WebAuthn relying party ID (your domain, e.g. 'app.example.com')"
  type        = string
}

variable "webauthn_rp_name" {
  description = "Human-readable WebAuthn relying party name"
  type        = string
  default     = "HSA Tracker"
}

variable "webauthn_origin" {
  description = "WebAuthn origin (full URL of the frontend, e.g. 'https://app.example.com')"
  type        = string
}

variable "cors_origins" {
  description = "Comma-separated list of allowed CORS origins for the API"
  type        = string
  default     = "http://localhost:3001"
}

variable "require_invite" {
  description = "Require an invite token to register"
  type        = bool
  default     = false
}

variable "vapid_public_key" {
  description = "VAPID public key for web push notifications (optional)"
  type        = string
  default     = ""
}

variable "vapid_private_key" {
  description = "VAPID private key for web push notifications (optional)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "vapid_claims_email" {
  description = "Email address for VAPID claims (optional)"
  type        = string
  default     = ""
}
