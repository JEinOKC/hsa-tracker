# ── IAM role for Lambda execution ─────────────────────────────────────────────

resource "aws_iam_role" "lambda_exec" {
  name = "hsa-tracker-lambda-exec"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# Basic Lambda execution (CloudWatch Logs)
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Allow Lambda to access the same S3 bucket the app already uses
resource "aws_iam_role_policy" "lambda_s3" {
  name = "hsa-tracker-lambda-s3"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket",
      ]
      Resource = [
        aws_s3_bucket.receipts.arn,
        "${aws_s3_bucket.receipts.arn}/*",
      ]
    }]
  })
}

# ── Teller credentials in Secrets Manager ─────────────────────────────────────
# Cert and private key are too large for Lambda env vars (5 KB limit).

resource "aws_secretsmanager_secret" "teller_credentials" {
  name        = "hsa-tracker/teller-credentials"
  description = "Teller TLS certificate and private key for HSA Tracker"
}

resource "aws_secretsmanager_secret_version" "teller_credentials" {
  secret_id = aws_secretsmanager_secret.teller_credentials.id
  secret_string = jsonencode({
    teller_cert_b64        = var.teller_cert_b64
    teller_private_key_b64 = var.teller_private_key_b64
  })
}

# Allow Lambda to read the Teller secret
resource "aws_iam_role_policy" "lambda_secrets" {
  name = "hsa-tracker-lambda-secrets"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [aws_secretsmanager_secret.teller_credentials.arn]
    }]
  })
}

# ── CloudWatch log group ───────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/hsa-tracker-backend"
  retention_in_days = 14
}

# ── Lambda function ────────────────────────────────────────────────────────────

resource "aws_lambda_function" "backend" {
  function_name = "hsa-tracker-backend"
  role          = aws_iam_role.lambda_exec.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.backend.repository_url}:${var.lambda_image_tag}"

  # 512 MB is comfortable for FastAPI + SQLAlchemy cold start.
  # Raise to 1024 MB if you notice cold-start timeouts.
  memory_size = 512
  timeout     = 30

  environment {
    variables = {
      APP_ENV                          = var.environment
      DEBUG                            = "false"
      DATABASE_URL                     = var.database_url
      SECRET_KEY                       = var.secret_key
      JWT_SECRET_KEY                   = var.jwt_secret_key
      JWT_ACCESS_TOKEN_EXPIRE_MINUTES  = tostring(var.jwt_access_token_expire_minutes)
      JWT_REFRESH_TOKEN_EXPIRE_DAYS    = tostring(var.jwt_refresh_token_expire_days)
      WEBAUTHN_RP_ID                   = var.webauthn_rp_id
      WEBAUTHN_RP_NAME                 = var.webauthn_rp_name
      WEBAUTHN_ORIGIN                  = var.webauthn_origin
      CORS_ORIGINS                     = var.cors_origins
      AWS_S3_BUCKET                    = aws_s3_bucket.receipts.id
      AWS_S3_REGION                    = var.aws_region
      REQUIRE_INVITE                   = tostring(var.require_invite)
      VAPID_PUBLIC_KEY                 = var.vapid_public_key
      VAPID_PRIVATE_KEY                = var.vapid_private_key
      VAPID_CLAIMS_EMAIL               = var.vapid_claims_email
      TELLER_SECRET_ARN                = aws_secretsmanager_secret.teller_credentials.arn
      TELLER_ENV                       = var.teller_env
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda,
    aws_iam_role_policy_attachment.lambda_basic,
  ]
}
