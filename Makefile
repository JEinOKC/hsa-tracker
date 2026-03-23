.PHONY: help setup-wizard dev-build dev-up dev-rebuild dev-down dev-logs prod-up prod-down prod-logs tf-init tf-plan tf-apply tf-destroy db-init db-migrate db-upgrade db-downgrade db-reset test-backend test-frontend test-all clean format lint

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
	DOCKER_COMPOSE_CMD := doppler run -- docker-compose
	RUN_CMD := doppler run --
else
	DOCKER_COMPOSE_CMD := docker-compose
	RUN_CMD :=
endif
else
	DOCKER_COMPOSE_CMD := docker-compose
	RUN_CMD :=
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

dev-up: ## Start development environment
	@echo "$(BLUE)Starting development environment...$(NC)"
	$(DOCKER_COMPOSE_CMD) -f docker-compose.dev.yml up -d
	@echo "$(GREEN)✓ Development environment started$(NC)"
	@echo "Frontend: http://localhost:3001 (configurable via FRONTEND_PORT)"
	@echo "Backend API: http://localhost:8001 (configurable via BACKEND_PORT)"
	@echo "API Docs: http://localhost:8001/docs"

dev-rebuild: ## Rebuild and restart development environment
	@echo "$(BLUE)Rebuilding and restarting development environment...$(NC)"
	$(DOCKER_COMPOSE_CMD) -f docker-compose.dev.yml up -d --build
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
	$(DOCKER_COMPOSE_CMD) up -d
	@echo "$(GREEN)✓ Production environment started$(NC)"
	@echo "Application: http://localhost:3000"

prod-down: ## Stop production environment
	@echo "$(BLUE)Stopping production environment...$(NC)"
	$(DOCKER_COMPOSE_CMD) down
	@echo "$(GREEN)✓ Production environment stopped$(NC)"

prod-logs: ## View production logs
	$(DOCKER_COMPOSE_CMD) logs -f

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

tf-init: ## Initialize Terraform
	@echo "$(BLUE)Initializing Terraform...$(NC)"
	cd terraform && terraform init
	@echo "$(GREEN)✓ Terraform initialized$(NC)"

tf-plan: ## Plan Terraform changes
	@echo "$(BLUE)Planning Terraform changes...$(NC)"
	cd terraform && terraform plan

tf-apply: ## Apply Terraform changes (create AWS infrastructure)
	@echo "$(BLUE)Applying Terraform changes...$(NC)"
	cd terraform && terraform apply
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

doppler-login: ## Login to Doppler
	@doppler login

doppler-setup: ## Set up Doppler for this project
	@doppler setup

doppler-secrets: ## View all secrets in Doppler
	@doppler secrets

doppler-open: ## Open Doppler dashboard in browser
	@doppler open
