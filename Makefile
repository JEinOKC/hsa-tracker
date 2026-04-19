.PHONY: help setup-wizard dev-build dev-up dev-rebuild dev-down dev-logs prod-up prod-down prod-logs tf-init tf-plan tf-apply tf-destroy tf-ecr-bootstrap db-init db-migrate db-migrate-prod db-upgrade db-downgrade db-reset test-backend test-frontend test-all clean format lint push-test generate-vapid generate-invite lambda-build lambda-push lambda-deploy build-check frontend-deploy deploy deploy-with-migrations

# Default target
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Detect if Doppler is available and configured
HAS_DOPPLER := $(shell command -v doppler 2>/dev/null)
DOPPLER_PROJECT := $(shell doppler configure get project --plain 2>/dev/null)
ifneq ($(HAS_DOPPLER),)
ifneq ($(DOPPLER_PROJECT),)
	DOCKER_COMPOSE_CMD := doppler run --config dev -- docker-compose
	RUN_CMD := doppler run --config dev --
	DOCKER_COMPOSE_CMD_PRD := doppler run --config prd -- docker-compose
	RUN_CMD_PRD := doppler run --config prd --
else
	DOCKER_COMPOSE_CMD := docker-compose
	RUN_CMD :=
	DOCKER_COMPOSE_CMD_PRD := docker-compose
	RUN_CMD_PRD :=
endif
else
	DOCKER_COMPOSE_CMD := docker-compose
	RUN_CMD :=
	DOCKER_COMPOSE_CMD_PRD := docker-compose
	RUN_CMD_PRD :=
endif

help: ## Show this help message
	@echo "$(BLUE)╔════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║             HSA Tracker - Available Commands               ║$(NC)"
	@echo "$(BLUE)╚════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(YELLOW)🚀 GETTING STARTED$(NC)"
	@echo "  $(GREEN)make setup-wizard$(NC)        Interactive setup wizard (RECOMMENDED)"
	@echo ""
	@echo "$(YELLOW)📦 DEVELOPMENT$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -v "GETTING STARTED" | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-22s$(NC) %s\n", $$1, $$2}'
ifdef DOPPLER_CONFIGURED
	@echo ""
	@echo "$(BLUE)✓ Doppler is configured and will be used for secrets$(NC)"
else
	@echo ""
	@echo "$(YELLOW)⚠ Doppler not configured. Using .env file for secrets$(NC)"
	@echo "  Run $(GREEN)make setup-wizard$(NC) to configure Doppler"
endif

# ==========================================
# Setup & Installation
# ==========================================

setup-wizard: ## 🎯 Run interactive setup wizard (START HERE!)
	@echo "$(BLUE)╔════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║             HSA Tracker - Setup Wizard                     ║$(NC)"
	@echo "$(BLUE)╚════════════════════════════════════════════════════════════╝$(NC)"
	@./scripts/setup-wizard.sh

setup: ## Quick setup (create config files from examples)
	@echo "$(BLUE)Running quick setup...$(NC)"
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "$(GREEN)✓ Created .env file from .env.example$(NC)"; \
		echo "$(YELLOW)⚠ Please edit .env with your configuration$(NC)"; \
	else \
		echo "$(YELLOW).env file already exists, skipping$(NC)"; \
	fi
	@if [ ! -f terraform/terraform.tfvars ]; then \
		cp terraform/examples/terraform.tfvars.example terraform/terraform.tfvars; \
		echo "$(GREEN)✓ Created terraform.tfvars$(NC)"; \
		echo "$(YELLOW)⚠ Please edit terraform/terraform.tfvars with your AWS settings$(NC)"; \
	else \
		echo "$(YELLOW)terraform.tfvars already exists, skipping$(NC)"; \
	fi
	@echo "$(GREEN)✓ Setup complete!$(NC)"
	@echo ""
	@echo "$(YELLOW)RECOMMENDED: Run $(GREEN)make setup-wizard$(NC) for guided setup$(YELLOW)$(NC)"

# ==========================================
# Development Commands
# ==========================================

dev-build: ## Build development containers (after code changes)
	@echo "$(BLUE)Building development containers...$(NC)"
	$(DOCKER_COMPOSE_CMD) -f docker-compose.dev.yml build
	@echo "$(GREEN)✓ Development containers built$(NC)"

dev-up: ## Start development environment (uses Doppler dev secrets)
	@echo "$(BLUE)Starting development environment...$(NC)"
	doppler run --config dev -- docker compose -f docker-compose.dev.yml up -d
	@echo "$(GREEN)✓ Development environment started$(NC)"
	@echo "Frontend: http://localhost:3001 (configurable via FRONTEND_PORT)"
	@echo "Backend API: http://localhost:8001 (configurable via BACKEND_PORT)"
	@echo "API Docs: http://localhost:8001/docs"

dev-rebuild-frontend: ## Rebuild frontend container (use after adding npm packages)
	@echo "$(BLUE)Rebuilding frontend container...$(NC)"
	$(DOCKER_COMPOSE_CMD) -f docker-compose.dev.yml rm -sf frontend
	docker volume rm hsa-tracker_frontend_node_modules 2>/dev/null || true
	$(DOCKER_COMPOSE_CMD) -f docker-compose.dev.yml up -d --build frontend
	@echo "$(GREEN)✓ Frontend rebuilt$(NC)"

dev-rebuild: ## Rebuild and restart development environment (uses Doppler dev secrets)
	@echo "$(BLUE)Rebuilding and restarting development environment...$(NC)"
	doppler run --config dev -- docker compose -f docker-compose.dev.yml up -d --build
	@echo "$(GREEN)✓ Development environment rebuilt and started$(NC)"
	@echo "Frontend: http://localhost:3001 (configurable via FRONTEND_PORT)"
	@echo "Backend API: http://localhost:8001 (configurable via BACKEND_PORT)"
	@echo "API Docs: http://localhost:8001/docs"

dev-down: ## Stop development environment
	@echo "$(BLUE)Stopping development environment...$(NC)"
	$(DOCKER_COMPOSE_CMD) -f docker-compose.dev.yml down
	@echo "$(GREEN)✓ Development environment stopped$(NC)"

dev-logs: ## View development logs
	$(DOCKER_COMPOSE_CMD) -f docker-compose.dev.yml logs -f

dev-shell-backend: ## Open shell in backend container
	$(DOCKER_COMPOSE_CMD) -f docker-compose.dev.yml exec backend /bin/bash

dev-shell-frontend: ## Open shell in frontend container
	$(DOCKER_COMPOSE_CMD) -f docker-compose.dev.yml exec frontend /bin/sh

# ==========================================
# Production Commands
# ==========================================

prod-up: ## Start production environment
	@echo "$(BLUE)Starting production environment...$(NC)"
	$(DOCKER_COMPOSE_CMD_PRD) up -d
	@echo "$(GREEN)✓ Production environment started$(NC)"
	@echo "Application: http://localhost:3000"

prod-down: ## Stop production environment
	@echo "$(BLUE)Stopping production environment...$(NC)"
	$(DOCKER_COMPOSE_CMD_PRD) down
	@echo "$(GREEN)✓ Production environment stopped$(NC)"

prod-logs: ## View production logs
	$(DOCKER_COMPOSE_CMD_PRD) logs -f

# ==========================================
# Database Commands
# ==========================================

db-init: ## Initialize database with first migration (run this once after first setup)
	@echo "$(BLUE)Creating initial database migration...$(NC)"
	$(DOCKER_COMPOSE_CMD) -f docker-compose.dev.yml exec backend alembic revision --autogenerate -m "Initial migration - user authentication tables"
	@echo "$(BLUE)Running migration...$(NC)"
	$(DOCKER_COMPOSE_CMD) -f docker-compose.dev.yml exec backend alembic upgrade head
	@echo "$(GREEN)✓ Database initialized$(NC)"

db-migrate: ## Create a new database migration
	@read -p "Enter migration name: " name; \
	$(DOCKER_COMPOSE_CMD) -f docker-compose.dev.yml exec backend alembic revision --autogenerate -m "$$name"
	@echo "$(GREEN)✓ Migration created$(NC)"

db-upgrade: ## Upgrade database to latest version
	@echo "$(BLUE)Upgrading database...$(NC)"
	$(DOCKER_COMPOSE_CMD) -f docker-compose.dev.yml exec backend alembic upgrade head
	@echo "$(GREEN)✓ Database upgraded$(NC)"

db-migrate-prod: ## Run Alembic migrations against production database (via Doppler prd config)
	@echo "$(BLUE)Running production migrations...$(NC)"
	doppler run --config prd -- sh -c '\
		docker run --rm \
			--platform linux/amd64 \
			-e DATABASE_URL \
			-e SECRET_KEY \
			-e JWT_SECRET_KEY \
			-e AWS_ACCESS_KEY_ID \
			-e AWS_SECRET_ACCESS_KEY \
			-e AWS_S3_BUCKET \
			-v "$(CURDIR)/backend:/app" \
			-w /app \
			python:3.11-slim \
			sh -c "pip install -q -r requirements.txt && alembic upgrade head"'
	@echo "$(GREEN)✓ Production migrations complete$(NC)"

db-downgrade: ## Downgrade database by one version
	@echo "$(YELLOW)Downgrading database...$(NC)"
	$(DOCKER_COMPOSE_CMD) -f docker-compose.dev.yml exec backend alembic downgrade -1
	@echo "$(GREEN)✓ Database downgraded$(NC)"

db-reset: ## Reset database (WARNING: Deletes all data!)
	@echo "$(RED)WARNING: This will delete all data!$(NC)"
	@read -p "Are you sure? (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		$(DOCKER_COMPOSE_CMD) -f docker-compose.dev.yml down -v; \
		$(DOCKER_COMPOSE_CMD) -f docker-compose.dev.yml up -d db; \
		sleep 5; \
		$(DOCKER_COMPOSE_CMD) -f docker-compose.dev.yml up -d backend; \
		echo "$(GREEN)✓ Database reset complete$(NC)"; \
	else \
		echo "$(YELLOW)Database reset cancelled$(NC)"; \
	fi

# ==========================================
# Terraform Commands
# ==========================================

# ==========================================
# Lambda Deployment Commands
# ==========================================

tf-ecr-bootstrap: ## Create ECR repository (one-time, before first deploy)
	@echo "$(BLUE)Creating ECR repository...$(NC)"
	doppler run -- sh -c '\
		unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN && \
		TF_VAR_database_url="$$DATABASE_URL" \
		TF_VAR_secret_key="$$SECRET_KEY" \
		TF_VAR_jwt_secret_key="$$JWT_SECRET_KEY" \
		TF_VAR_webauthn_rp_id="$$WEBAUTHN_RP_ID" \
		TF_VAR_webauthn_origin="$$FRONTEND_URL" \
		TF_VAR_cors_origins="$$FRONTEND_URL" \
		TF_VAR_vapid_public_key="$$VAPID_PUBLIC_KEY" \
		TF_VAR_vapid_private_key="$$VAPID_PRIVATE_KEY" \
		TF_VAR_vapid_claims_email="$$VAPID_CLAIMS_EMAIL" \
		TF_VAR_allowed_cors_origins="[\"$$FRONTEND_URL\"]" \
		TF_VAR_cloudflare_api_token="$$CLOUDFLARE_API_TOKEN" \
		TF_VAR_cloudflare_zone_id="$$CLOUDFLARE_ZONE_ID" \
		TF_VAR_cloudflare_account_id="$$CLOUDFLARE_ACCOUNT_ID" \
		TF_VAR_frontend_domain="$$FRONTEND_DOMAIN" \
		TF_VAR_api_custom_domain="$$API_CUSTOM_DOMAIN" \
		TF_VAR_github_repo="$$GITHUB_REPO" \
		TF_VAR_teller_app_id="$$TELLER_APP_ID" \
		TF_VAR_teller_cert_b64="$$TELLER_CERT_B64" \
		TF_VAR_teller_private_key_b64="$$TELLER_PRIVATE_KEY_B64" \
		TF_VAR_teller_env="$$TELLER_ENV" \
		TF_VAR_require_invite="$${REQUIRE_INVITE:-true}" \
		terraform -chdir=terraform apply \
			-target=aws_ecr_repository.backend \
			-target=aws_ecr_lifecycle_policy.backend \
			-auto-approve'
	@echo "$(GREEN)✓ ECR repository created$(NC)"

generate-invite: ## Manage invite tokens. ENV=prd|dev (default: dev), CMD=create|list|"revoke <token>"
	doppler run --config $${ENV:-dev} -- sh -c 'docker-compose -f docker-compose.dev.yml exec -e DATABASE_URL="$$DATABASE_URL" backend python scripts/generate_invite.py $${CMD:-create}'

lambda-build: ## Build the Lambda Docker image
	@echo "$(BLUE)Building Lambda Docker image...$(NC)"
	docker build --platform linux/amd64 -f backend/Dockerfile.lambda -t hsa-tracker-backend:latest ./backend
	@echo "$(GREEN)✓ Lambda image built$(NC)"

lambda-push: ## Authenticate to ECR, push the Lambda image, and force Lambda to use it
	@echo "$(BLUE)Pushing Lambda image to ECR...$(NC)"
	@ACCOUNT_ID=$$(aws sts get-caller-identity --query Account --output text) && \
	REGION=$$(terraform -chdir=terraform output -raw s3_bucket_region 2>/dev/null || echo "us-east-1") && \
	ECR_REPO="$$ACCOUNT_ID.dkr.ecr.$$REGION.amazonaws.com/hsa-tracker-backend" && \
	aws ecr get-login-password --region $$REGION | docker login --username AWS --password-stdin "$$ACCOUNT_ID.dkr.ecr.$$REGION.amazonaws.com" && \
	docker tag hsa-tracker-backend:latest "$$ECR_REPO:latest" && \
	docker push "$$ECR_REPO:latest" && \
	echo "$(BLUE)Updating Lambda function code...$(NC)" && \
	aws lambda update-function-code \
		--function-name hsa-tracker-backend \
		--region $$REGION \
		--image-uri "$$ECR_REPO:latest" \
		--query 'LastUpdateStatus' \
		--output text && \
	aws lambda wait function-updated \
		--function-name hsa-tracker-backend \
		--region $$REGION
	@echo "$(GREEN)✓ Lambda image pushed and function updated$(NC)"

lambda-deploy: lambda-build lambda-push ## Build and push Lambda image (run tf-ecr-bootstrap first if ECR doesn't exist)

deploy: lambda-deploy db-migrate-prod frontend-deploy ## Deploy Lambda, run migrations, and deploy frontend

build-check: ## Dry-run the frontend build with dev secrets (catches TS/build errors before deploying)
	@echo "$(BLUE)Running frontend build check with dev secrets...$(NC)"
	doppler run --config dev -- sh -c '\
		cd frontend && \
		VITE_API_URL="$${VITE_API_URL:-http://localhost:8001/api/v1}" \
		VITE_VAPID_PUBLIC_KEY="$$VAPID_PUBLIC_KEY" \
		VITE_WEBAUTHN_RP_ID="$${WEBAUTHN_RP_ID:-localhost}" \
		VITE_TELLER_APP_ID="$$TELLER_APP_ID" \
		VITE_TELLER_ENV="$${TELLER_ENV:-sandbox}" \
		npm run build'
	@echo "$(GREEN)✓ Build check passed — safe to deploy$(NC)"

frontend-deploy: ## Build and deploy frontend to Cloudflare Pages (manual — does not auto-deploy on git push)
	@echo "$(BLUE)Building frontend...$(NC)"
	doppler run --config prd -- sh -c '\
		cd frontend && \
		VITE_API_URL="https://$$API_CUSTOM_DOMAIN/api/v1" \
		VITE_VAPID_PUBLIC_KEY="$$VAPID_PUBLIC_KEY" \
		VITE_WEBAUTHN_RP_ID="$$WEBAUTHN_RP_ID" \
		VITE_TELLER_APP_ID="$$TELLER_APP_ID" \
		VITE_TELLER_ENV="$$TELLER_ENV" \
		npm run build && \
		npx wrangler pages deploy dist \
			--project-name hsa-tracker \
			--branch main'
	@echo "$(GREEN)✓ Frontend deployed to Cloudflare Pages$(NC)"

# ==========================================
# Terraform Commands
# ==========================================

tf-init: ## Initialize Terraform
	@echo "$(BLUE)Initializing Terraform...$(NC)"
	cd terraform && terraform init
	@echo "$(GREEN)✓ Terraform initialized$(NC)"

tf-plan: ## Plan Terraform changes
	@echo "$(BLUE)Planning Terraform changes...$(NC)"
	doppler run -- sh -c '\
		unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN && \
		TF_VAR_database_url="$$DATABASE_URL" \
		TF_VAR_secret_key="$$SECRET_KEY" \
		TF_VAR_jwt_secret_key="$$JWT_SECRET_KEY" \
		TF_VAR_webauthn_rp_id="$$WEBAUTHN_RP_ID" \
		TF_VAR_webauthn_origin="$$FRONTEND_URL" \
		TF_VAR_cors_origins="$$FRONTEND_URL" \
		TF_VAR_vapid_public_key="$$VAPID_PUBLIC_KEY" \
		TF_VAR_vapid_private_key="$$VAPID_PRIVATE_KEY" \
		TF_VAR_vapid_claims_email="$$VAPID_CLAIMS_EMAIL" \
		TF_VAR_allowed_cors_origins="[\"$$FRONTEND_URL\"]" \
		TF_VAR_cloudflare_api_token="$$CLOUDFLARE_API_TOKEN" \
		TF_VAR_cloudflare_zone_id="$$CLOUDFLARE_ZONE_ID" \
		TF_VAR_cloudflare_account_id="$$CLOUDFLARE_ACCOUNT_ID" \
		TF_VAR_frontend_domain="$$FRONTEND_DOMAIN" \
		TF_VAR_api_custom_domain="$$API_CUSTOM_DOMAIN" \
		TF_VAR_github_repo="$$GITHUB_REPO" \
		TF_VAR_teller_app_id="$$TELLER_APP_ID" \
		TF_VAR_teller_cert_b64="$$TELLER_CERT_B64" \
		TF_VAR_teller_private_key_b64="$$TELLER_PRIVATE_KEY_B64" \
		TF_VAR_teller_env="$$TELLER_ENV" \
		TF_VAR_require_invite="$${REQUIRE_INVITE:-true}" \
		terraform -chdir=terraform plan'

tf-apply: ## Apply Terraform changes (create AWS infrastructure)
	@echo "$(BLUE)Applying Terraform changes...$(NC)"
	doppler run -- sh -c '\
		unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN && \
		TF_VAR_database_url="$$DATABASE_URL" \
		TF_VAR_secret_key="$$SECRET_KEY" \
		TF_VAR_jwt_secret_key="$$JWT_SECRET_KEY" \
		TF_VAR_webauthn_rp_id="$$WEBAUTHN_RP_ID" \
		TF_VAR_webauthn_origin="$$FRONTEND_URL" \
		TF_VAR_cors_origins="$$FRONTEND_URL" \
		TF_VAR_vapid_public_key="$$VAPID_PUBLIC_KEY" \
		TF_VAR_vapid_private_key="$$VAPID_PRIVATE_KEY" \
		TF_VAR_vapid_claims_email="$$VAPID_CLAIMS_EMAIL" \
		TF_VAR_allowed_cors_origins="[\"$$FRONTEND_URL\"]" \
		TF_VAR_cloudflare_api_token="$$CLOUDFLARE_API_TOKEN" \
		TF_VAR_cloudflare_zone_id="$$CLOUDFLARE_ZONE_ID" \
		TF_VAR_cloudflare_account_id="$$CLOUDFLARE_ACCOUNT_ID" \
		TF_VAR_frontend_domain="$$FRONTEND_DOMAIN" \
		TF_VAR_api_custom_domain="$$API_CUSTOM_DOMAIN" \
		TF_VAR_github_repo="$$GITHUB_REPO" \
		TF_VAR_teller_app_id="$$TELLER_APP_ID" \
		TF_VAR_teller_cert_b64="$$TELLER_CERT_B64" \
		TF_VAR_teller_private_key_b64="$$TELLER_PRIVATE_KEY_B64" \
		TF_VAR_teller_env="$$TELLER_ENV" \
		TF_VAR_require_invite="$${REQUIRE_INVITE:-true}" \
		terraform -chdir=terraform apply'
	@echo "$(GREEN)✓ AWS infrastructure created$(NC)"
	@echo "$(YELLOW)Remember to update your secrets with the output values!$(NC)"

tf-destroy: ## Destroy Terraform infrastructure (WARNING: Deletes S3 bucket!)
	@echo "$(RED)WARNING: This will delete your S3 bucket and all receipts!$(NC)"
	@read -p "Are you sure? Type 'destroy' to confirm: " confirm; \
	if [ "$$confirm" = "destroy" ]; then \
		cd terraform && terraform destroy; \
		echo "$(GREEN)✓ Infrastructure destroyed$(NC)"; \
	else \
		echo "$(YELLOW)Destroy cancelled$(NC)"; \
	fi

# ==========================================
# Testing Commands
# ==========================================

test-backend: ## Run backend tests
	@echo "$(BLUE)Running backend tests...$(NC)"
	$(DOCKER_COMPOSE_CMD) -f docker-compose.dev.yml exec backend pytest
	@echo "$(GREEN)✓ Backend tests complete$(NC)"

test-frontend: ## Run frontend tests
	@echo "$(BLUE)Running frontend tests...$(NC)"
	$(DOCKER_COMPOSE_CMD) -f docker-compose.dev.yml exec frontend npm test
	@echo "$(GREEN)✓ Frontend tests complete$(NC)"

test-all: test-backend test-frontend ## Run all tests

# ==========================================
# Utility Commands
# ==========================================

clean: ## Clean up build artifacts and caches
	@echo "$(BLUE)Cleaning up...$(NC)"
	rm -rf backend/__pycache__
	rm -rf backend/.pytest_cache
	rm -rf backend/htmlcov
	rm -rf backend/.coverage
	rm -rf frontend/node_modules
	rm -rf frontend/dist
	$(DOCKER_COMPOSE_CMD) -f docker-compose.dev.yml down -v
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

format: ## Format code (backend: black, frontend: prettier)
	@echo "$(BLUE)Formatting code...$(NC)"
	$(DOCKER_COMPOSE_CMD) -f docker-compose.dev.yml exec backend black app/
	$(DOCKER_COMPOSE_CMD) -f docker-compose.dev.yml exec frontend npm run format
	@echo "$(GREEN)✓ Code formatted$(NC)"

lint: ## Lint code (backend: flake8, frontend: eslint)
	@echo "$(BLUE)Linting code...$(NC)"
	$(DOCKER_COMPOSE_CMD) -f docker-compose.dev.yml exec backend flake8 app/
	$(DOCKER_COMPOSE_CMD) -f docker-compose.dev.yml exec frontend npm run lint
	@echo "$(GREEN)✓ Linting complete$(NC)"

# ==========================================
# Doppler Commands
# ==========================================

# ==========================================
# Push Notification Commands
# ==========================================

generate-vapid: ## Generate VAPID keys for Web Push (run once, add output to .env/Doppler)
	@echo "$(BLUE)Generating VAPID keys...$(NC)"
	$(RUN_CMD) docker-compose -f docker-compose.dev.yml exec backend python scripts/generate_vapid_keys.py

push-test: ## Send a test push notification. Usage: make push-test USER=username [TITLE="Title"] [MSG="Body"]
	@echo "$(BLUE)Sending test push notification...$(NC)"
	doppler run --config prd -- python backend/scripts/send_test_push.py \
		"$${TITLE:-Test Message}" \
		"$${MSG:-Test push notification}" \
		$(if $(USER),--user $(USER),)

doppler-login: ## Login to Doppler
	@doppler login

doppler-setup: ## Set up Doppler for this project
	@doppler setup

doppler-secrets: ## View all secrets in Doppler
	@doppler secrets

doppler-open: ## Open Doppler dashboard in browser
	@doppler open
