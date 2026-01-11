#!/bin/bash

# HSA Tracker - Interactive Setup Wizard
# This script guides you through setting up HSA Tracker step-by-step

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

ask_yes_no() {
    while true; do
        read -p "$1 (y/n): " yn
        case $yn in
            [Yy]* ) return 0;;
            [Nn]* ) return 1;;
            * ) echo "Please answer yes or no.";;
        esac
    done
}

# Welcome message
clear
print_header "Welcome to HSA Tracker Setup Wizard!"
echo "This wizard will guide you through setting up HSA Tracker."
echo "We'll help you:"
echo "  1. Choose how to manage secrets (Doppler or .env files)"
echo "  2. Set up AWS infrastructure for receipt storage"
echo "  3. Configure the application"
echo "  4. Start the application"
echo ""
echo "Don't worry if you're new to AWS or Terraform - we'll explain everything!"
echo ""
read -p "Press Enter to continue..."

# Step 1: Check prerequisites
print_header "Step 1: Checking Prerequisites"

# Check Docker
if command -v docker &> /dev/null; then
    print_success "Docker is installed"
else
    print_error "Docker is not installed"
    echo "Please install Docker Desktop: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Check Docker Compose
if docker compose version &> /dev/null || docker-compose --version &> /dev/null; then
    print_success "Docker Compose is installed"
else
    print_error "Docker Compose is not installed"
    exit 1
fi

# Check if Docker is running
if docker info &> /dev/null; then
    print_success "Docker is running"
else
    print_error "Docker is not running"
    echo "Please start Docker Desktop and try again"
    exit 1
fi

# Step 2: Detect existing configuration
print_header "Step 2: Checking Existing Setup"

# Check if secrets are already configured
SECRETS_CONFIGURED=false
USE_DOPPLER=false

# Check Doppler first (preferred)
if command -v doppler &> /dev/null && doppler setup --no-interactive get project &> /dev/null 2>&1; then
    if doppler secrets get SECRET_KEY &> /dev/null 2>&1; then
        print_success "Found existing Doppler configuration with secrets"
        SECRETS_CONFIGURED=true
        USE_DOPPLER=true
    fi
fi

# Fall back to .env if Doppler not configured
if [ "$SECRETS_CONFIGURED" = false ] && [ -f ".env" ] && grep -q "SECRET_KEY" .env 2>/dev/null; then
    print_success "Found existing .env file with secrets"
    SECRETS_CONFIGURED=true
    USE_DOPPLER=false
fi

# Check if Terraform has been applied
TERRAFORM_APPLIED=false
if [ -f "terraform/terraform.tfstate" ] && [ -s "terraform/terraform.tfstate" ]; then
    print_success "Terraform infrastructure already created"
    TERRAFORM_APPLIED=true
    # Extract existing values
    cd terraform
    if terraform output s3_bucket_name &> /dev/null; then
        S3_BUCKET=$(terraform output -raw s3_bucket_name)
        S3_REGION=$(terraform output -raw s3_bucket_region)
        S3_ACCESS_KEY=$(terraform output -raw aws_access_key_id)
        S3_SECRET_KEY=$(terraform output -raw aws_secret_access_key)
        print_info "S3 Bucket: $S3_BUCKET"
    fi
    cd ..
fi

# Check if containers are running
CONTAINERS_RUNNING=false
if docker-compose -f docker-compose.dev.yml ps --services --filter "status=running" 2>/dev/null | grep -q .; then
    print_success "Docker containers are already running"
    CONTAINERS_RUNNING=true
fi

echo ""
if [ "$SECRETS_CONFIGURED" = true ] && [ "$TERRAFORM_APPLIED" = true ]; then
    print_success "Setup appears to be complete!"
    echo ""
    echo "What would you like to do?"
    echo "  1) Just start/restart containers (recommended if setup is done)"
    echo "  2) Reconfigure everything from scratch"
    echo "  3) Exit"
    echo ""
    read -p "Choose an option [1]: " QUICK_OPTION
    QUICK_OPTION=${QUICK_OPTION:-1}

    if [ "$QUICK_OPTION" = "1" ]; then
        print_info "Skipping to container startup..."
        SKIP_TO_CONTAINERS=true
    elif [ "$QUICK_OPTION" = "3" ]; then
        echo "Exiting. Run 'make dev-up' to start containers."
        exit 0
    else
        SKIP_TO_CONTAINERS=false
    fi
else
    SKIP_TO_CONTAINERS=false
fi

if [ "$SKIP_TO_CONTAINERS" = false ]; then

# Step 3: Choose secrets management
print_header "Step 3: Choose Secrets Management"
echo "HSA Tracker needs to store sensitive information like:"
echo "  - Database passwords"
echo "  - JWT secret keys"
echo "  - AWS credentials"
echo ""
echo "You have two options:"
echo ""
echo "Option 1: Doppler (Recommended)"
echo "  ✓ Secure cloud-based secrets management"
echo "  ✓ Team collaboration support"
echo "  ✓ Automatic syncing across environments"
echo "  ✓ Free tier available"
echo "  ✗ Requires Doppler account"
echo ""
echo "Option 2: .env file (Simple)"
echo "  ✓ No external dependencies"
echo "  ✓ Works offline"
echo "  ✗ Secrets stored locally in plain text"
echo "  ✗ Hard to share with team"
echo ""

if [ "$SECRETS_CONFIGURED" = true ]; then
    echo "Detected existing configuration."
    if ask_yes_no "Keep existing secrets configuration?"; then
        print_info "Using existing configuration"
    else
        SECRETS_CONFIGURED=false
    fi
fi

if [ "$SECRETS_CONFIGURED" = false ] && ask_yes_no "Do you want to use Doppler for secrets management?"; then
    USE_DOPPLER=true

    # Check for Doppler CLI
    if command -v doppler &> /dev/null; then
        print_success "Doppler CLI is installed"
    else
        print_warning "Doppler CLI is not installed"
        echo ""
        echo "Let's install it:"
        echo ""

        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo "Run: brew install dopplerhq/cli/doppler"
        elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
            echo "Run: curl -sLf https://cli.doppler.com/install.sh | sh"
        else
            echo "Visit: https://docs.doppler.com/docs/install-cli"
        fi
        echo ""
        read -p "Press Enter after installing Doppler CLI..."

        if ! command -v doppler &> /dev/null; then
            print_error "Doppler CLI still not found"
            exit 1
        fi
    fi

    # Doppler login
    print_info "Checking Doppler authentication..."
    if doppler configure get token &> /dev/null; then
        print_success "Already logged in to Doppler"
    else
        echo "Please log in to Doppler:"
        doppler login
    fi

    # Create Doppler project
    print_header "Creating Doppler Project"
    echo "We'll create a Doppler project to store your HSA Tracker secrets."
    echo ""
    read -p "Enter a name for your Doppler project [hsa-tracker]: " DOPPLER_PROJECT
    DOPPLER_PROJECT=${DOPPLER_PROJECT:-hsa-tracker}

    # Check if project exists
    if doppler projects get $DOPPLER_PROJECT &> /dev/null; then
        print_warning "Project '$DOPPLER_PROJECT' already exists"
        if ask_yes_no "Use existing project?"; then
            print_success "Using existing project: $DOPPLER_PROJECT"
        else
            echo "Please run the wizard again with a different project name"
            exit 1
        fi
    else
        doppler projects create $DOPPLER_PROJECT --description "HSA Tracker secrets"
        print_success "Created Doppler project: $DOPPLER_PROJECT"
    fi

    # Set up environments
    print_info "Setting up Doppler environment..."
    doppler setup --project $DOPPLER_PROJECT --config dev --no-interactive
    print_success "Doppler configured for this directory"

else
    USE_DOPPLER=false
    print_info "Will use .env file for secrets"
fi

# Step 4: AWS Setup
print_header "Step 4: AWS Infrastructure Setup"

if [ "$TERRAFORM_APPLIED" = true ]; then
    print_success "AWS infrastructure already configured"
    echo "S3 Bucket: $S3_BUCKET"
    echo "Region: $S3_REGION"
    echo ""
    if ! ask_yes_no "Do you want to reconfigure AWS infrastructure?"; then
        print_info "Using existing AWS infrastructure"
    else
        TERRAFORM_APPLIED=false
    fi
fi

if [ "$TERRAFORM_APPLIED" = false ]; then

echo "HSA Tracker stores receipt images in AWS S3 (Simple Storage Service)."
echo ""
echo "What is S3?"
echo "  - Cloud storage for files (like Dropbox)"
echo "  - You only pay for what you use (~\$1-5/month for typical usage)"
echo "  - Your receipts stay in YOUR AWS account (full control)"
echo ""
echo "We'll use Terraform to automatically create:"
echo "  - An S3 bucket (storage container for receipts)"
echo "  - Access credentials (so the app can upload/download)"
echo ""

if ask_yes_no "Do you want to set up AWS infrastructure now?"; then

    # Check for AWS CLI
    if command -v aws &> /dev/null; then
        print_success "AWS CLI is installed"
    else
        print_warning "AWS CLI is not installed (optional but recommended)"
        echo "You can install it later from: https://aws.amazon.com/cli/"
    fi

    # Check for Terraform
    if command -v terraform &> /dev/null; then
        print_success "Terraform is installed"
    else
        print_error "Terraform is not installed"
        echo ""
        echo "Please install Terraform:"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo "Run: brew install terraform"
        elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
            echo "Visit: https://developer.hashicorp.com/terraform/downloads"
        else
            echo "Visit: https://developer.hashicorp.com/terraform/downloads"
        fi
        exit 1
    fi

    # Get AWS credentials
    print_header "AWS Credentials"
    echo "Terraform needs AWS credentials to create resources."
    echo ""
    echo "If you don't have an AWS account yet:"
    echo "  1. Go to https://aws.amazon.com"
    echo "  2. Click 'Create an AWS Account'"
    echo "  3. Follow the signup process (free tier available)"
    echo ""
    echo "To get your credentials:"
    echo "  1. Log in to AWS Console: https://console.aws.amazon.com"
    echo "  2. Click your name (top right) → Security credentials"
    echo "  3. Scroll to 'Access keys' → Create access key"
    echo "  4. Choose 'CLI' use case"
    echo "  5. Copy the Access Key ID and Secret Access Key"
    echo ""
    read -p "Press Enter when you have your AWS credentials ready..."

    echo ""
    read -p "Enter your AWS Access Key ID: " AWS_ACCESS_KEY_ID
    read -sp "Enter your AWS Secret Access Key: " AWS_SECRET_ACCESS_KEY
    echo ""

    # Validate credentials
    print_info "Validating AWS credentials..."
    export AWS_ACCESS_KEY_ID
    export AWS_SECRET_ACCESS_KEY

    if aws sts get-caller-identity &> /dev/null; then
        print_success "AWS credentials are valid!"
    else
        print_error "AWS credentials are invalid"
        echo "Please check your Access Key ID and Secret Access Key"
        exit 1
    fi

    # Terraform configuration
    print_header "Terraform Configuration"
    echo "Let's configure your S3 bucket:"
    echo ""

    read -p "Enter AWS region [us-east-1]: " AWS_REGION
    AWS_REGION=${AWS_REGION:-us-east-1}

    read -p "Enter S3 bucket name prefix [hsa-tracker-receipts]: " BUCKET_PREFIX
    BUCKET_PREFIX=${BUCKET_PREFIX:-hsa-tracker-receipts}

    # Create terraform.tfvars
    cat > terraform/terraform.tfvars <<EOF
aws_region = "$AWS_REGION"
environment = "production"
bucket_name_prefix = "$BUCKET_PREFIX"
enable_versioning = true
lifecycle_transition_days = 365
lifecycle_expiration_days = 90
enable_kms_encryption = false
EOF

    print_success "Created terraform/terraform.tfvars"

    # Run Terraform
    print_header "Creating AWS Infrastructure"
    echo "Terraform will now create your S3 bucket and access credentials."
    echo "This will take about 30-60 seconds."
    echo ""

    cd terraform
    terraform init
    terraform plan
    echo ""

    if ask_yes_no "Review the plan above. Proceed with creating infrastructure?"; then
        terraform apply -auto-approve

        # Extract outputs
        S3_BUCKET=$(terraform output -raw s3_bucket_name)
        S3_REGION=$(terraform output -raw s3_bucket_region)
        S3_ACCESS_KEY=$(terraform output -raw aws_access_key_id)
        S3_SECRET_KEY=$(terraform output -raw aws_secret_access_key)

        print_success "AWS infrastructure created!"
        echo ""
        echo "Your S3 bucket: $S3_BUCKET"
        echo "Region: $S3_REGION"
        echo ""
    else
        print_warning "Skipping infrastructure creation"
        cd ..
        exit 0
    fi

    cd ..

else
    print_warning "Skipping AWS setup"
    echo "You can run this wizard again later to set up AWS"
    echo "For now, the app will still work but receipt uploads won't function"

    # Use dummy values
    S3_BUCKET="not-configured"
    S3_REGION="us-east-1"
    S3_ACCESS_KEY="not-configured"
    S3_SECRET_KEY="not-configured"
fi

fi  # End of TERRAFORM_APPLIED check

# Step 5: Application Configuration
if [ "$SECRETS_CONFIGURED" = false ]; then
print_header "Step 5: Application Configuration"
echo "Let's set up the rest of your application secrets..."
echo ""

# Generate secrets
print_info "Generating secure random secrets..."
if command -v openssl &> /dev/null; then
    SECRET_KEY=$(openssl rand -hex 32)
    JWT_SECRET_KEY=$(openssl rand -hex 32)
else
    SECRET_KEY=$(cat /dev/urandom | LC_ALL=C tr -dc 'a-zA-Z0-9' | fold -w 64 | head -n 1)
    JWT_SECRET_KEY=$(cat /dev/urandom | LC_ALL=C tr -dc 'a-zA-Z0-9' | fold -w 64 | head -n 1)
fi
print_success "Generated SECRET_KEY and JWT_SECRET_KEY"

# Database password
DB_PASSWORD=$(openssl rand -hex 16)
print_success "Generated database password"

# Save configuration
if [ "$USE_DOPPLER" = true ]; then
    print_header "Saving Secrets to Doppler"

    # Application secrets
    doppler secrets set SECRET_KEY="$SECRET_KEY" --silent
    doppler secrets set JWT_SECRET_KEY="$JWT_SECRET_KEY" --silent
    doppler secrets set DATABASE_PASSWORD="$DB_PASSWORD" --silent

    # AWS secrets (if configured)
    doppler secrets set AWS_S3_BUCKET="$S3_BUCKET" --silent
    doppler secrets set AWS_S3_REGION="$S3_REGION" --silent
    doppler secrets set AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY" --silent
    doppler secrets set AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY" --silent

    # Database config
    doppler secrets set DATABASE_TYPE="postgresql" --silent
    doppler secrets set DATABASE_URL="postgresql://hsatracker:$DB_PASSWORD@db:5432/hsatracker" --silent

    # Postgres config
    doppler secrets set POSTGRES_USER="hsatracker" --silent
    doppler secrets set POSTGRES_PASSWORD="$DB_PASSWORD" --silent
    doppler secrets set POSTGRES_DB="hsatracker" --silent

    print_success "All secrets saved to Doppler!"

else
    print_header "Creating .env File"

    cat > .env <<EOF
# Application Settings
APP_NAME=HSA Tracker
APP_ENV=development
DEBUG=true
SECRET_KEY=$SECRET_KEY

# Database Configuration
DATABASE_TYPE=postgresql
DATABASE_URL=postgresql://hsatracker:$DB_PASSWORD@db:5432/hsatracker

# AWS S3 Configuration
AWS_ACCESS_KEY_ID=$S3_ACCESS_KEY
AWS_SECRET_ACCESS_KEY=$S3_SECRET_KEY
AWS_S3_BUCKET=$S3_BUCKET
AWS_S3_REGION=$S3_REGION

# Authentication Settings
JWT_SECRET_KEY=$JWT_SECRET_KEY
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# WebAuthn Configuration
WEBAUTHN_RP_ID=localhost
WEBAUTHN_RP_NAME=HSA Tracker
WEBAUTHN_ORIGIN=http://localhost:3000

# CORS Settings
CORS_ORIGINS=http://localhost:3000,http://localhost:80

# File Upload Settings
MAX_UPLOAD_SIZE_MB=10
ALLOWED_MIME_TYPES=image/jpeg,image/png,image/heic,application/pdf

# Frontend Configuration
VITE_API_URL=http://localhost:8000/api/v1
VITE_WEBAUTHN_RP_ID=localhost

# PostgreSQL Configuration
POSTGRES_USER=hsatracker
POSTGRES_PASSWORD=$DB_PASSWORD
POSTGRES_DB=hsatracker
EOF

    print_success "Created .env file"
fi

fi  # End of SECRETS_CONFIGURED check

fi  # End of SKIP_TO_CONTAINERS check

# Step 6: Start the application
print_header "Step 6: Starting the Application"

if [ "$USE_DOPPLER" = true ]; then
    print_info "Starting containers with Doppler..."
    doppler run -- docker-compose -f docker-compose.dev.yml up -d
else
    print_info "Starting containers..."
    docker-compose -f docker-compose.dev.yml up -d
fi

# Wait for database to be ready
print_info "Waiting for database to start..."
sleep 10

# Run migrations
print_info "Setting up database..."
if [ "$USE_DOPPLER" = true ]; then
    doppler run -- docker-compose -f docker-compose.dev.yml exec -T backend alembic upgrade head || {
        print_warning "Migration failed, generating migration first..."
        doppler run -- docker-compose -f docker-compose.dev.yml exec -T backend alembic revision --autogenerate -m "Add user authentication tables"
        doppler run -- docker-compose -f docker-compose.dev.yml exec -T backend alembic upgrade head
    }
else
    docker-compose -f docker-compose.dev.yml exec -T backend alembic upgrade head || {
        print_warning "Migration failed, generating migration first..."
        docker-compose -f docker-compose.dev.yml exec -T backend alembic revision --autogenerate -m "Add user authentication tables"
        docker-compose -f docker-compose.dev.yml exec -T backend alembic upgrade head
    }
fi

print_success "Database set up complete!"

# Final success message
print_header "🎉 Setup Complete!"
echo ""
print_success "HSA Tracker is now running!"
echo ""
echo "Access your application:"
echo "  Frontend: http://localhost:3000"
echo "  Backend API: http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo ""
echo "Next steps:"
echo "  1. Open http://localhost:3000 in your browser"
echo "  2. Click 'Create one' to register your first user"
echo "  3. Start tracking your HSA expenses!"
echo ""

if [ "$USE_DOPPLER" = true ]; then
    echo "Your secrets are stored in Doppler:"
    echo "  Project: $DOPPLER_PROJECT"
    echo "  Config: dev"
    echo ""
    echo "To view your secrets: doppler secrets"
    echo "To edit secrets: doppler secrets set KEY=value"
else
    print_warning "Your secrets are stored in .env file"
    echo "Keep this file secure and never commit it to git!"
fi

echo ""
echo "To stop the application: make dev-down"
echo "To view logs: make dev-logs"
echo ""
print_success "Happy tracking!"
