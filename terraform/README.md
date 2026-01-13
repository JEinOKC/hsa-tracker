# HSA Tracker - AWS Infrastructure Setup

This directory contains Terraform configuration to set up the required AWS infrastructure for HSA Tracker.

## What Gets Created

1. **S3 Bucket** for storing receipt images and PDFs
   - Private bucket with all public access blocked
   - Server-side encryption (AES256 or KMS)
   - Versioning enabled (configurable)
   - CORS configuration for browser uploads
   - Lifecycle policy for cost optimization

2. **IAM User** with minimal permissions
   - Only able to read/write/delete from the receipts bucket
   - Access keys for application authentication

3. **KMS Key** (optional) for enhanced encryption

## Prerequisites

1. **AWS Account**: You need an active AWS account
2. **AWS CLI**: Installed and configured with credentials
   ```bash
   aws configure
   ```
3. **Terraform**: Installed (version >= 1.0)
   ```bash
   # macOS
   brew install terraform

   # Windows (with Chocolatey)
   choco install terraform

   # Linux
   # See: https://developer.hashicorp.com/terraform/downloads
   ```

## Quick Start

### 1. Configure Your Settings

```bash
cd terraform
cp examples/terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` to customize:
- AWS region
- Bucket name prefix
- Lifecycle policies
- Encryption settings

### 2. Initialize Terraform

```bash
terraform init
```

### 3. Preview Changes

```bash
terraform plan
```

This shows you what will be created without making any changes.

### 4. Create Infrastructure

```bash
terraform apply
```

Type `yes` when prompted to confirm.

### 5. Save Credentials

After successful completion, Terraform will display:
- S3 bucket name
- AWS region
- IAM access key ID
- IAM secret access key

**Copy these values to your `.env` file in the project root!**

To view them again:
```bash
# View all outputs
terraform output

# View secret key (sensitive)
terraform output aws_secret_access_key
```

## Configuration Options

### Basic Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `aws_region` | AWS region for resources | `us-east-1` |
| `environment` | Environment name | `production` |
| `bucket_name_prefix` | Prefix for bucket name | `hsa-tracker-receipts` |

### Advanced Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `enable_versioning` | Enable S3 versioning | `true` |
| `lifecycle_transition_days` | Days before moving to Glacier | `365` |
| `lifecycle_expiration_days` | Days before deleting old versions | `0` (disabled) |
| `enable_kms_encryption` | Use KMS instead of SSE-S3 | `false` |

### Cost Considerations

**Standard Setup (default)**:
- S3 storage: ~$0.023/GB/month
- S3 requests: Minimal (pay per request)
- Encryption: Free (AES256)
- **Estimated cost**: $1-5/month for typical usage

**With KMS Encryption**:
- Additional: $1/month for KMS key
- Additional: $0.03 per 10,000 requests
- **Estimated cost**: $2-10/month

**With Glacier Transition** (after 1 year):
- Glacier storage: ~$0.004/GB/month
- Retrieval costs apply when accessing old receipts

## Security Features

### Encryption
- **At rest**: All objects encrypted (AES256 or KMS)
- **In transit**: HTTPS/TLS only

### Access Control
- **Bucket**: Private, blocks all public access
- **IAM**: Minimal permissions (read/write/delete only)
- **CORS**: Restricted to your application origin

### Versioning
- Protects against accidental deletion
- Allows recovery of previous versions
- Can set expiration for old versions

## Updating Infrastructure

To modify your infrastructure:

1. Edit `terraform.tfvars`
2. Run `terraform plan` to preview changes
3. Run `terraform apply` to apply changes

## Destroying Infrastructure

**WARNING**: This will delete your S3 bucket and all receipts!

```bash
terraform destroy
```

Only do this if you're completely done with the application and have backed up any important receipts.

## Troubleshooting

### "Bucket already exists"
Bucket names are globally unique. Change `bucket_name_prefix` in `terraform.tfvars`.

### "Access Denied" errors
Ensure your AWS CLI is configured with valid credentials:
```bash
aws sts get-caller-identity
```

### "Region not supported"
Some AWS regions have restricted access. Try `us-east-1` or `us-west-2`.

## Updating CORS Origins

After deployment, update the CORS configuration with your actual domain:

1. Edit `s3.tf`
2. Update `allowed_origins` in the CORS configuration
3. Run `terraform apply`

Example:
```hcl
allowed_origins = ["https://yourdomain.com", "http://localhost:3000"]
```

## State Management

Terraform stores state in `terraform.tfstate`. This file contains sensitive information.

**Important**:
- Keep `terraform.tfstate` secure
- Don't commit it to version control (.gitignore handles this)
- Consider using remote state (S3 backend) for team environments

## Support

For issues with:
- **Terraform**: Check [Terraform AWS Provider docs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- **AWS**: Check [AWS S3 documentation](https://docs.aws.amazon.com/s3/)
- **HSA Tracker**: Open an issue in the main repository
