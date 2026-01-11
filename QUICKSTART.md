# Quick Start Guide

This guide will get you from `git clone` to a running application in under 15 minutes.

## Prerequisites

- **Docker Desktop** installed and running
- **Make** installed (comes with macOS/Linux, Windows users can use WSL or Git Bash)
- **AWS Account** (for S3 receipt storage)
- **Terraform** installed ([download here](https://www.terraform.io/downloads))

## Step-by-Step Setup

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/hsa-tracker.git
cd hsa-tracker
```

### 2. Create Configuration Files

```bash
make setup
```

This creates:
- `.env` from `.env.example`
- `terraform/terraform.tfvars` from the example

### 3. Configure Environment Variables

Edit `.env` and set these required values:

```bash
# Generate random secrets (use: openssl rand -hex 32)
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here

# Database (leave as-is for Docker setup)
DATABASE_TYPE=postgresql
DATABASE_URL=postgresql://hsatracker:hsatracker@db:5432/hsatracker

# AWS (will get these from Terraform in next step)
AWS_ACCESS_KEY_ID=will-get-from-terraform
AWS_SECRET_ACCESS_KEY=will-get-from-terraform
AWS_S3_BUCKET=will-get-from-terraform
AWS_S3_REGION=us-east-1
```

**Quick way to generate secrets:**
```bash
# On macOS/Linux:
openssl rand -hex 32

# Or use this Python one-liner:
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Set Up AWS Infrastructure

```bash
# Configure AWS credentials (if not already done)
aws configure

# Edit Terraform variables (optional - defaults are fine)
nano terraform/terraform.tfvars

# Initialize and apply Terraform
cd terraform
terraform init
terraform apply
# Type 'yes' when prompted
cd ..
```

**Copy the outputs** from Terraform into your `.env` file:
- `AWS_S3_BUCKET=<bucket name from output>`
- `AWS_ACCESS_KEY_ID=<access key from output>`
- `AWS_SECRET_ACCESS_KEY=<secret key from output>`

### 5. Start the Application

```bash
make dev-up
```

This will:
- Start PostgreSQL database
- Start backend API server (with hot-reload)
- Start frontend dev server (with hot-reload)

**First-time startup takes 2-3 minutes** to download images and install dependencies.

### 6. Access the Application

Once all containers are running:

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs (interactive Swagger UI)

### 7. View Logs (Optional)

```bash
make dev-logs
```

Press `Ctrl+C` to exit logs.

## What You Can Do Right Now

The application is **partially functional**:

✅ **What Works:**
- Navigate between pages (Dashboard, Transactions, Login)
- View API documentation at http://localhost:8000/docs
- See system categories at http://localhost:8000/api/v1/categories/
- Health check endpoint at http://localhost:8000/api/v1/health

⚠️ **What's Not Implemented Yet:**
- Authentication (endpoints return 501 Not Implemented)
- Database models (no migrations created yet)
- Transaction CRUD (placeholders only)
- Receipt upload to S3
- Family management

This is expected - you have the **complete scaffolding** ready for development.

## Next Development Steps

To continue building:

1. **Create database models** in `backend/app/models/`
2. **Generate migrations**: `make db-migrate`
3. **Implement endpoints** in `backend/app/api/v1/endpoints/`
4. **Build frontend components** in `frontend/src/components/`

See [CONTRIBUTING.md](./CONTRIBUTING.md) for detailed development guidelines.

## Stopping the Application

```bash
make dev-down
```

## Troubleshooting

### Port already in use

If you see "port already in use" errors:

```bash
# Check what's using the port
lsof -i :3000  # Frontend
lsof -i :8000  # Backend
lsof -i :5432  # Database

# Stop the process or change ports in docker-compose.dev.yml
```

### Docker daemon not running

Make sure Docker Desktop is running:
- **macOS**: Open Docker Desktop app
- **Linux**: `sudo systemctl start docker`
- **Windows**: Open Docker Desktop

### Database connection failed

```bash
# Reset the database
make dev-down
make dev-up
```

### Terraform errors

**"NoSuchBucket" or credential errors:**
```bash
# Verify AWS credentials
aws sts get-caller-identity

# Re-run Terraform
cd terraform
terraform destroy  # Clean up first
terraform apply
```

### Module not found errors

```bash
# Rebuild containers
make dev-down
docker-compose -f docker-compose.dev.yml build --no-cache
make dev-up
```

## Getting Help

- Check [README.md](./README.md) for detailed documentation
- See [CONTRIBUTING.md](./CONTRIBUTING.md) for development setup
- Open an issue on GitHub

## Summary

You should now have:
- ✅ All containers running
- ✅ Frontend accessible at localhost:3000
- ✅ Backend API at localhost:8000
- ✅ AWS S3 bucket provisioned
- ✅ Database ready for migrations

**Time to start building!** 🚀
