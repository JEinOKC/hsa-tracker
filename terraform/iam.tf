# IAM user for application access to S3
resource "aws_iam_user" "hsa_tracker_app" {
  name = "hsa-tracker-app-${random_id.bucket_suffix.hex}"

  tags = {
    Name        = "HSA Tracker Application User"
    Description = "IAM user for HSA Tracker application to access S3 receipts bucket"
  }
}

# Access key for the IAM user
resource "aws_iam_access_key" "hsa_tracker_app" {
  user = aws_iam_user.hsa_tracker_app.name
}

# IAM policy for S3 access (minimal permissions)
resource "aws_iam_user_policy" "hsa_tracker_s3_access" {
  name = "hsa-tracker-s3-access"
  user = aws_iam_user.hsa_tracker_app.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Effect = "Allow"
          Action = [
            "s3:PutObject",
            "s3:GetObject",
            "s3:DeleteObject",
            "s3:ListBucket"
          ]
          Resource = [
            aws_s3_bucket.receipts.arn,
            "${aws_s3_bucket.receipts.arn}/*"
          ]
        }
      ],
      # Only include KMS statement if KMS encryption is enabled
      var.enable_kms_encryption ? [
        {
          Effect = "Allow"
          Action = [
            "kms:Decrypt",
            "kms:Encrypt",
            "kms:GenerateDataKey"
          ]
          Resource = [aws_kms_key.receipts[0].arn]
        }
      ] : []
    )
  })
}
