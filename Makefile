.PHONY: help dev-up dev-down dev-logs prod-up prod-down prod-logs tf-init tf-plan tf-apply tf-destroy db-migrate db-upgrade db-downgrade db-reset test-backend test-frontend test-all clean format lint

# Default target
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)HSA Tracker - Available Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

# Development Commands
dev-up: ## Start development environment
	@echo "$(BLUE)Starting development environment...$(NC)"
	docker-compose -f docker-compose.dev.yml up -d
	@echo "$(GREEN)✓ Development environment started$(NC)"
	@echo "Frontend: http://localhost:3000"
	@echo "Backend API: http://localhost:8000"
	@echo "API Docs: http://localhost:8000/docs"

dev-down: ## Stop development environment
	@echo "$(BLUE)Stopping development environment...$(NC)"
	docker-compose -f docker-compose.dev.yml down
	@echo "$(GREEN)✓ Development environment stopped$(NC)"

dev-logs: ## View development logs
	docker-compose -f docker-compose.dev.yml logs -f

dev-shell-backend: ## Open shell in backend container
	docker-compose -f docker-compose.dev.yml exec backend /bin/bash

dev-shell-frontend: ## Open shell in frontend container
	docker-compose -f docker-compose.dev.yml exec frontend /bin/sh

# Production Commands
prod-up: ## Start production environment
	@echo "$(BLUE)Starting production environment...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✓ Production environment started$(NC)"
	@echo "Application: http://localhost:3000"

prod-down: ## Stop production environment
	@echo "$(BLUE)Stopping production environment...$(NC)"
	docker-compose down
	@echo "$(GREEN)✓ Production environment stopped$(NC)"

prod-logs: ## View production logs
	docker-compose logs -f

# Database Commands
db-migrate: ## Create a new database migration
	@read -p "Enter migration name: " name; \
	docker-compose -f docker-compose.dev.yml exec backend alembic revision --autogenerate -m "$$name"
	@echo "$(GREEN)✓ Migration created$(NC)"

db-upgrade: ## Upgrade database to latest version
	@echo "$(BLUE)Upgrading database...$(NC)"
	docker-compose -f docker-compose.dev.yml exec backend alembic upgrade head
	@echo "$(GREEN)✓ Database upgraded$(NC)"

db-downgrade: ## Downgrade database by one version
	@echo "$(YELLOW)Downgrading database...$(NC)"
	docker-compose -f docker-compose.dev.yml exec backend alembic downgrade -1
	@echo "$(GREEN)✓ Database downgraded$(NC)"

db-reset: ## Reset database (WARNING: Deletes all data!)
	@echo "$(RED)WARNING: This will delete all data!$(NC)"
	@read -p "Are you sure? (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		docker-compose -f docker-compose.dev.yml down -v; \
		docker-compose -f docker-compose.dev.yml up -d db; \
		sleep 5; \
		docker-compose -f docker-compose.dev.yml up -d backend; \
		echo "$(GREEN)✓ Database reset complete$(NC)"; \
	else \
		echo "$(YELLOW)Database reset cancelled$(NC)"; \
	fi

# Terraform Commands
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
	@echo "$(YELLOW)Remember to update your .env file with the output values!$(NC)"

tf-destroy: ## Destroy Terraform infrastructure (WARNING: Deletes S3 bucket!)
	@echo "$(RED)WARNING: This will delete your S3 bucket and all receipts!$(NC)"
	@read -p "Are you sure? Type 'destroy' to confirm: " confirm; \
	if [ "$$confirm" = "destroy" ]; then \
		cd terraform && terraform destroy; \
		echo "$(GREEN)✓ Infrastructure destroyed$(NC)"; \
	else \
		echo "$(YELLOW)Destroy cancelled$(NC)"; \
	fi

# Testing Commands
test-backend: ## Run backend tests
	@echo "$(BLUE)Running backend tests...$(NC)"
	docker-compose -f docker-compose.dev.yml exec backend pytest
	@echo "$(GREEN)✓ Backend tests complete$(NC)"

test-frontend: ## Run frontend tests
	@echo "$(BLUE)Running frontend tests...$(NC)"
	docker-compose -f docker-compose.dev.yml exec frontend npm test
	@echo "$(GREEN)✓ Frontend tests complete$(NC)"

test-all: test-backend test-frontend ## Run all tests

# Utility Commands
clean: ## Clean up build artifacts and caches
	@echo "$(BLUE)Cleaning up...$(NC)"
	rm -rf backend/__pycache__
	rm -rf backend/.pytest_cache
	rm -rf backend/htmlcov
	rm -rf backend/.coverage
	rm -rf frontend/node_modules
	rm -rf frontend/dist
	docker-compose -f docker-compose.dev.yml down -v
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

format: ## Format code (backend: black, frontend: prettier)
	@echo "$(BLUE)Formatting code...$(NC)"
	docker-compose -f docker-compose.dev.yml exec backend black app/
	docker-compose -f docker-compose.dev.yml exec frontend npm run format
	@echo "$(GREEN)✓ Code formatted$(NC)"

lint: ## Lint code (backend: flake8, frontend: eslint)
	@echo "$(BLUE)Linting code...$(NC)"
	docker-compose -f docker-compose.dev.yml exec backend flake8 app/
	docker-compose -f docker-compose.dev.yml exec frontend npm run lint
	@echo "$(GREEN)✓ Linting complete$(NC)"

# Setup Commands
setup: ## Initial setup (create .env, init terraform)
	@echo "$(BLUE)Running initial setup...$(NC)"
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
	@echo "$(BLUE)Next steps:$(NC)"
	@echo "1. Edit .env with your configuration"
	@echo "2. Edit terraform/terraform.tfvars with your AWS settings"
	@echo "3. Run: make tf-init && make tf-apply"
	@echo "4. Update .env with Terraform outputs"
	@echo "5. Run: make dev-up"
