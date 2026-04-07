# HSA Tracker — Infrastructure & Deployment

This directory contains Terraform configuration for all HSA Tracker cloud infrastructure.

## What Gets Created

| Resource | Purpose |
|---|---|
| **S3 Bucket** | Receipt image/PDF storage |
| **IAM User** | App-level S3 access (scoped to bucket only) |
| **ECR Repository** | Stores the Lambda Docker image |
| **Lambda Function** | Runs the FastAPI backend (via Mangum) |
| **API Gateway (HTTP v2)** | Public HTTPS endpoint for the Lambda |
| **ACM Certificate** | TLS cert for the API custom domain |
| **CloudWatch Log Group** | Lambda logs, 14-day retention |
| **Cloudflare Pages** | Hosts the React frontend (if `cloudflare_enabled = true`) |
| **Cloudflare DNS Records** | API subdomain, frontend subdomain, ACM validation |

---

## Prerequisites

- **AWS CLI** configured with admin credentials (`aws configure`)
- **Terraform** >= 1.0
- **Docker** (for building the Lambda image)
- **Doppler CLI** (for secrets management — see project root README)
- **PostgreSQL database** with a pooled connection string (e.g. Neon, Supabase, or any Postgres with PgBouncer)
- **Cloudflare account** (if using Cloudflare DNS/Pages)

---

## Deployment Options

### Option A: Lambda + Cloudflare (recommended, effectively free)

Backend runs on AWS Lambda. Frontend hosted on Cloudflare Pages. DNS managed by Cloudflare.

Set `cloudflare_enabled = true` in `terraform.tfvars` (default for this repo).

### Option B: Lambda + any static host

Backend runs on AWS Lambda with a raw API Gateway URL. Frontend deployed to Netlify, Vercel, S3+CloudFront, or any static host. DNS managed manually.

Set `cloudflare_enabled = false` in `terraform.tfvars` and set `VITE_API_URL` to the API Gateway URL in your frontend host's build settings.

### Option C: Self-hosted server

Run the backend with Docker Compose on any VPS. No Lambda or ECR needed. See the project root README for Docker-based deployment.

---

## First Deploy (Step by Step)

### 1. Configure secrets

All sensitive values are managed via Doppler. Switch to your production config:

```bash
doppler configure set config prd
```

The following Doppler secrets are required:

| Doppler key | Notes |
|---|---|
| `DATABASE_URL` | Pooled PostgreSQL URL with PgBouncer (`...?pgbouncer=true&sslmode=require`) |
| `SECRET_KEY` | Random 32-byte hex — `python -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_SECRET_KEY` | Same command, different value |
| `WEBAUTHN_RP_ID` | Your frontend domain, e.g. `hsa.example.com` |
| `FRONTEND_URL` | Full frontend URL, e.g. `https://hsa.example.com` |
| `VAPID_PUBLIC_KEY` | From `make generate-vapid` |
| `VAPID_PRIVATE_KEY` | From `make generate-vapid` |
| `VAPID_CLAIMS_EMAIL` | Your email address |
| `TELLER_APP_ID` | Your Teller application ID |
| `CLOUDFLARE_API_TOKEN` | Token with Zone:DNS:Edit + Account:Cloudflare Pages:Edit |
| `CLOUDFLARE_ZONE_ID` | From Cloudflare dashboard → your domain → Zone ID |
| `CLOUDFLARE_ACCOUNT_ID` | From Cloudflare dashboard → account home |
| `FRONTEND_DOMAIN` | e.g. `hsa.example.com` |
| `API_CUSTOM_DOMAIN` | e.g. `hsa-api.example.com` |
| `GITHUB_REPO` | e.g. `youruser/hsa-tracker` |

### 2. Initialize Terraform

```bash
make tf-init
```

### 3. Create ECR repository (one-time bootstrap)

Lambda needs a Docker image before it can be created, and ECR must exist before the image can be pushed.

```bash
make tf-ecr-bootstrap
```

### 4. Build and push the Lambda image

```bash
make lambda-deploy
```

This builds `backend/Dockerfile.lambda` and pushes it to ECR as `:latest`.

### 5. Deploy all infrastructure

```bash
make tf-apply
```

This creates Lambda, API Gateway, ACM certificate, Cloudflare Pages project, and all DNS records in one pass. ACM certificate validation is automated via Cloudflare DNS — no manual steps required.

### 6. Run database migrations

Lambda does not run Alembic on startup. Run migrations once against your database before the first request:

```bash
DATABASE_URL=<your-neon-pooled-url> docker exec hsa-tracker-backend-dev alembic upgrade head
```

---

## Subsequent Deploys

When you push new backend code:

```bash
make lambda-deploy   # rebuild and push new image to ECR
```

Lambda will use the new image on its next cold start. To force an immediate update:

```bash
aws lambda update-function-code \
  --function-name hsa-tracker-backend \
  --image-uri $(terraform -chdir=terraform output -raw ecr_repository_url):latest
```

Frontend deploys automatically via Cloudflare Pages on every push to `main`.

---

## Configuration Reference

### Non-sensitive variables (set in `terraform.tfvars`)

| Variable | Description | Default |
|---|---|---|
| `aws_region` | AWS region | `us-east-1` |
| `environment` | Environment tag | `production` |
| `bucket_name_prefix` | S3 bucket name prefix | `hsa-tracker-receipts` |
| `enable_versioning` | S3 versioning | `true` |
| `lifecycle_transition_days` | Days before Glacier transition | `365` |
| `lifecycle_expiration_days` | Days before expiring old versions | `90` |
| `enable_kms_encryption` | KMS vs AES256 encryption | `false` |
| `lambda_image_tag` | ECR image tag to deploy | `latest` |
| `cloudflare_enabled` | Enable Cloudflare automation | `false` |

### Sensitive variables (set via Doppler, mapped in Makefile)

See the Doppler secrets table above.

---

## Cost Estimate

For a personal/hobby deployment:

| Service | Cost |
|---|---|
| Lambda | Free (1M requests/month free tier) |
| API Gateway | Free (~$1/million requests after free tier) |
| ECR | ~$0.03–0.05/month (image storage) |
| CloudWatch Logs | Free (under 5 GB/month) |
| ACM Certificate | Free |
| S3 | ~$0.023/GB/month |
| Cloudflare Pages | Free |
| PostgreSQL (e.g. Neon) | Free tier available |
| **Total** | **Effectively $0** for personal use |

---

## Troubleshooting

### "Access Denied" on tf-plan/tf-apply
The Makefile unsets `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` from Doppler so Terraform uses your local `~/.aws/credentials`. Ensure `aws configure` is set up with admin credentials.

### Lambda fails to create — image not found
Run `make tf-ecr-bootstrap` then `make lambda-deploy` before `make tf-apply`.

### ACM certificate stuck in PENDING_VALIDATION
Terraform waits for DNS validation automatically. If it times out, check that the ACM validation CNAME was created in Cloudflare (it should be — Terraform creates it). DNS propagation can take a few minutes.

### "Bucket already exists"
Bucket names are globally unique. Change `bucket_name_prefix` in `terraform.tfvars`.
