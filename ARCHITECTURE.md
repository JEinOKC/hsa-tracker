# HSA Tracker - Technical Architecture

## Overview

This document defines the technical architecture for the HSA Tracker application based on the following core principles:

- **Self-hosted first**: Simple deployment on Mac/Windows/Linux
- **Containerized**: Docker-based with minimal setup
- **Secure by default**: Modern auth (passkeys/2FA), AWS best practices via IaC
- **Extensible**: Custom UI capabilities, future Databricks integration
- **Start small**: MVP focuses on core expense tracking

---

## Technology Stack

### Backend
**Python 3.11+ with FastAPI**

*Rationale:*
- FastAPI provides excellent performance, automatic API documentation (OpenAPI/Swagger)
- Modern async support for scalability
- Strong type hints for maintainability
- Native compatibility with future Databricks integration (Python-based)
- Rich ecosystem for data processing (pandas, numpy for future analytics)
- Excellent library support for WebAuthn, TOTP, AWS SDK

*Key Libraries:*
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `sqlalchemy` - ORM with support for both PostgreSQL and SQLite
- `alembic` - Database migrations
- `pydantic` - Data validation and settings management
- `boto3` - AWS S3 SDK
- `py-webauthn` - WebAuthn/Passkey support
- `pyotp` - TOTP for 2FA
- `python-multipart` - File upload handling
- `pillow` - Image processing and thumbnail generation
- `python-jose` - JWT tokens for session management
- `passlib` - Password hashing (for optional password fallback)
- `pytest` - Testing framework

### Frontend
**React 18+ with TypeScript**

*Rationale:*
- Component-based architecture allows for easy extensibility
- Large ecosystem with extensive UI libraries
- TypeScript provides type safety and better developer experience
- Support for CSS modules, styled-components, or plain CSS for customization
- Can expose component override system for advanced users

*Key Libraries:*
- `react` + `react-dom` - Core framework
- `typescript` - Type safety
- `vite` - Fast build tool and dev server
- `react-router-dom` - Client-side routing
- `@tanstack/react-query` - Server state management
- `zustand` or `jotai` - Client state management (lightweight)
- `react-hook-form` - Form handling
- `zod` - Schema validation
- `tailwindcss` - Utility-first CSS (easily customizable)
- `shadcn/ui` - Accessible component library (fully customizable)
- `recharts` - Charts and visualizations
- `date-fns` - Date manipulation
- `@simplewebauthn/browser` - WebAuthn client
- `react-dropzone` - File upload component

### Database
**Dual Support: PostgreSQL (production) + SQLite (simple deployments)**

*Configuration:*
- PostgreSQL 16+ for multi-user/production deployments
- SQLite for single-user or development
- SQLAlchemy ORM abstracts database differences
- Connection string configuration for external databases
- Bundled PostgreSQL container in docker-compose for easy setup

### File Storage
**AWS S3**

*Features:*
- User provides their own S3 bucket credentials
- Terraform IaC for bucket provisioning with best practices:
  - Private bucket with encryption at rest (SSE-S3 or SSE-KMS)
  - Versioning enabled for receipt history
  - Lifecycle policies for cost optimization
  - CORS configuration for direct uploads
  - IAM user with minimal permissions (PutObject, GetObject, DeleteObject)
- Pre-signed URLs for secure file uploads/downloads
- Optional local filesystem storage for development/testing

### Infrastructure as Code
**Terraform**

*Structure:*
```
terraform/
├── main.tf              # Main configuration
├── variables.tf         # Input variables
├── outputs.tf           # Output values (bucket name, IAM credentials)
├── s3.tf               # S3 bucket configuration
├── iam.tf              # IAM user and policies
├── README.md           # Setup instructions
└── examples/
    └── terraform.tfvars.example
```

*Features:*
- Single `terraform apply` command to create all AWS resources
- Outputs IAM credentials securely
- Configurable bucket name, region, and retention policies
- Optional KMS key for enhanced encryption

### Authentication
**Passkeys (WebAuthn) + TOTP 2FA**

*Implementation:*
- **Passkeys (Primary)**: WebAuthn-based passwordless authentication
  - Biometric authentication (Face ID, Touch ID, Windows Hello)
  - Hardware security keys (YubiKey, etc.)
  - Platform authenticators
- **TOTP 2FA**: Time-based one-time passwords
  - Compatible with Google Authenticator, Authy, 1Password, etc.
  - QR code generation for easy setup
  - Backup codes for account recovery
- **Optional Password**: Fallback for users without passkey support
- **JWT Sessions**: Short-lived access tokens + refresh tokens
- **Multi-tenant ready**: Tenant isolation at database level

### Containerization
**Docker + Docker Compose**

*Containers:*
1. **backend**: FastAPI application
2. **frontend**: React app served by nginx
3. **db** (optional): PostgreSQL database
4. **redis** (future): For caching and background jobs

*Features:*
- Multi-stage builds for optimized image sizes
- Health checks for all services
- Volume mounts for data persistence
- Environment-based configuration
- Production and development compose files
- Hot-reload for development

---

## System Architecture

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          User's Browser                          │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  React Frontend (Port 3000)                                 │ │
│  │  - Passkey/TOTP auth UI                                     │ │
│  │  - Expense entry forms                                      │ │
│  │  - Receipt upload (drag & drop)                            │ │
│  │  - Dashboard & reports                                      │ │
│  │  - Customizable themes/CSS                                  │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────┬───────────────────────────────────────────────┘
                  │ HTTPS/WSS
                  │
┌─────────────────▼───────────────────────────────────────────────┐
│                    Docker Compose Stack                          │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Nginx (Port 80/443)                                        │ │
│  │  - Reverse proxy                                            │ │
│  │  - SSL termination                                          │ │
│  │  - Static file serving                                      │ │
│  └────────────────────┬───────────────────────────────────────┘ │
│                       │                                          │
│  ┌────────────────────▼───────────────────────────────────────┐ │
│  │  FastAPI Backend (Port 8000)                                │ │
│  │  - REST API endpoints                                       │ │
│  │  - WebAuthn/TOTP handlers                                   │ │
│  │  - S3 upload/download logic                                 │ │
│  │  - Business logic & validation                              │ │
│  │  - JWT token management                                     │ │
│  └────────────────────┬───────────────────────────────────────┘ │
│                       │                                          │
│  ┌────────────────────▼───────────────────────────────────────┐ │
│  │  PostgreSQL / SQLite                                        │ │
│  │  - User accounts & families                                 │ │
│  │  - Expense transactions                                     │ │
│  │  - Categories & tags                                        │ │
│  │  - Receipt metadata                                         │ │
│  │  - Auth credentials                                         │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────┬───────────────────────────────────────────────┘
                  │
                  │ boto3 SDK
                  │
┌─────────────────▼───────────────────────────────────────────────┐
│                      AWS S3 Bucket                               │
│  (User's AWS Account)                                            │
│  - Receipt images (JPEG, PNG, HEIC, PDF)                        │
│  - Encrypted at rest                                             │
│  - Versioning enabled                                            │
│  - Pre-signed URLs for secure access                            │
└──────────────────────────────────────────────────────────────────┘
```

### Database Schema (Core MVP Entities)

```sql
-- Users and Authentication
users
  - id (UUID, PK)
  - email (unique)
  - display_name
  - is_active
  - created_at
  - updated_at

user_passkeys
  - id (UUID, PK)
  - user_id (FK -> users)
  - credential_id (unique)
  - public_key
  - sign_count
  - created_at

user_totp
  - id (UUID, PK)
  - user_id (FK -> users, unique)
  - secret (encrypted)
  - is_verified
  - created_at

user_backup_codes
  - id (UUID, PK)
  - user_id (FK -> users)
  - code_hash
  - used_at

-- Multi-tenancy
families
  - id (UUID, PK)
  - name
  - created_at
  - updated_at

family_members
  - id (UUID, PK)
  - family_id (FK -> families)
  - user_id (FK -> users, nullable) -- Null for non-user dependents
  - name
  - relationship (enum: self, spouse, child, other)
  - date_of_birth
  - is_tax_dependent
  - is_active
  - created_at
  - updated_at

-- HSA Accounts
hsa_accounts
  - id (UUID, PK)
  - family_id (FK -> families)
  - name
  - account_holder_id (FK -> family_members)
  - current_balance (decimal)
  - contribution_limit_type (enum: individual, family)
  - created_at
  - updated_at

hsa_contributions
  - id (UUID, PK)
  - hsa_account_id (FK -> hsa_accounts)
  - amount (decimal)
  - contribution_date
  - contribution_type (enum: employee, employer, other)
  - tax_year (integer)
  - notes
  - created_at

-- Expense Categories
expense_categories
  - id (UUID, PK)
  - family_id (FK -> families, nullable) -- Null for system categories
  - name
  - description
  - is_hsa_eligible
  - parent_category_id (FK -> expense_categories, nullable)
  - is_system_category
  - created_at

-- Transactions
transactions
  - id (UUID, PK)
  - family_id (FK -> families)
  - hsa_account_id (FK -> hsa_accounts, nullable)
  - family_member_id (FK -> family_members) -- Who expense is for
  - category_id (FK -> expense_categories)
  - transaction_date
  - amount (decimal)
  - merchant_name
  - description
  - payment_method (enum: hsa_card, personal, other)
  - reimbursement_status (enum: not_needed, pending, reimbursed, not_seeking)
  - reimbursed_date
  - tax_year (integer)
  - created_by_user_id (FK -> users)
  - created_at
  - updated_at

-- Receipts
receipts
  - id (UUID, PK)
  - transaction_id (FK -> transactions)
  - file_name
  - file_size
  - mime_type
  - s3_key
  - s3_bucket
  - upload_date
  - uploaded_by_user_id (FK -> users)
  - thumbnail_s3_key (nullable)
  - created_at
```

### API Structure

```
/api/v1
├── /auth
│   ├── POST   /register
│   ├── POST   /login/passkey/options
│   ├── POST   /login/passkey/verify
│   ├── POST   /login/totp
│   ├── POST   /logout
│   ├── POST   /refresh
│   ├── GET    /me
│   ├── POST   /setup-passkey/options
│   ├── POST   /setup-passkey/verify
│   ├── POST   /setup-totp
│   ├── POST   /verify-totp
│   └── POST   /generate-backup-codes
├── /families
│   ├── GET    /
│   ├── POST   /
│   ├── GET    /:id
│   ├── PUT    /:id
│   └── DELETE /:id
├── /family-members
│   ├── GET    /               (filtered by family)
│   ├── POST   /
│   ├── GET    /:id
│   ├── PUT    /:id
│   └── DELETE /:id
├── /hsa-accounts
│   ├── GET    /               (filtered by family)
│   ├── POST   /
│   ├── GET    /:id
│   ├── PUT    /:id
│   └── DELETE /:id
├── /contributions
│   ├── GET    /               (filtered by account)
│   ├── POST   /
│   ├── GET    /:id
│   ├── PUT    /:id
│   └── DELETE /:id
├── /categories
│   ├── GET    /               (system + family custom)
│   ├── POST   /               (create custom)
│   ├── GET    /:id
│   ├── PUT    /:id
│   └── DELETE /:id
├── /transactions
│   ├── GET    /               (with filters: date, member, category)
│   ├── POST   /
│   ├── GET    /:id
│   ├── PUT    /:id
│   ├── DELETE /:id
│   └── GET    /export         (CSV/JSON export)
├── /receipts
│   ├── GET    /               (filtered by transaction)
│   ├── POST   /upload-url     (get pre-signed S3 URL)
│   ├── POST   /               (create receipt record after S3 upload)
│   ├── GET    /:id
│   ├── GET    /:id/download   (pre-signed download URL)
│   └── DELETE /:id
├── /reports
│   ├── GET    /dashboard
│   ├── GET    /spending-by-category
│   ├── GET    /spending-by-member
│   ├── GET    /tax-summary/:year
│   └── GET    /contribution-status
└── /health
    └── GET    /               (health check)
```

---

## Project Structure

```
hsa-tracker/
├── .github/
│   └── workflows/
│       ├── backend-tests.yml
│       ├── frontend-tests.yml
│       └── docker-build.yml
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI app entry point
│   │   ├── config.py                  # Settings management
│   │   ├── dependencies.py            # Dependency injection
│   │   ├── database.py                # DB connection
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── endpoints/
│   │   │   │   │   ├── auth.py
│   │   │   │   │   ├── families.py
│   │   │   │   │   ├── family_members.py
│   │   │   │   │   ├── hsa_accounts.py
│   │   │   │   │   ├── transactions.py
│   │   │   │   │   ├── receipts.py
│   │   │   │   │   ├── categories.py
│   │   │   │   │   └── reports.py
│   │   │   │   └── router.py
│   │   ├── models/                    # SQLAlchemy models
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── family.py
│   │   │   ├── hsa_account.py
│   │   │   ├── transaction.py
│   │   │   └── receipt.py
│   │   ├── schemas/                   # Pydantic schemas
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── family.py
│   │   │   ├── transaction.py
│   │   │   └── receipt.py
│   │   ├── services/                  # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py
│   │   │   ├── s3_service.py
│   │   │   ├── transaction_service.py
│   │   │   └── report_service.py
│   │   ├── utils/
│   │   │   ├── __init__.py
│   │   │   ├── security.py            # WebAuthn, TOTP, JWT
│   │   │   ├── validators.py
│   │   │   └── date_helpers.py
│   │   └── db/
│   │       └── migrations/            # Alembic migrations
│   │           └── versions/
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_auth.py
│   │   ├── test_transactions.py
│   │   └── test_reports.py
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── pyproject.toml                 # Project metadata
├── frontend/
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── main.tsx                   # Entry point
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── ui/                    # shadcn/ui components
│   │   │   ├── auth/
│   │   │   │   ├── PasskeyLogin.tsx
│   │   │   │   └── TotpSetup.tsx
│   │   │   ├── transactions/
│   │   │   │   ├── TransactionForm.tsx
│   │   │   │   ├── TransactionList.tsx
│   │   │   │   └── ReceiptUpload.tsx
│   │   │   ├── dashboard/
│   │   │   │   └── Dashboard.tsx
│   │   │   └── layout/
│   │   │       ├── Header.tsx
│   │   │       └── Sidebar.tsx
│   │   ├── pages/
│   │   │   ├── Login.tsx
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Transactions.tsx
│   │   │   ├── FamilyMembers.tsx
│   │   │   ├── Reports.tsx
│   │   │   └── Settings.tsx
│   │   ├── hooks/
│   │   │   ├── useAuth.ts
│   │   │   ├── useTransactions.ts
│   │   │   └── useReceipts.ts
│   │   ├── services/
│   │   │   ├── api.ts                 # Axios instance
│   │   │   ├── auth.ts
│   │   │   └── webauthn.ts
│   │   ├── store/                     # State management
│   │   │   ├── authStore.ts
│   │   │   └── familyStore.ts
│   │   ├── types/
│   │   │   ├── api.ts
│   │   │   └── models.ts
│   │   ├── styles/
│   │   │   ├── globals.css
│   │   │   └── custom-theme.css       # User-customizable
│   │   └── utils/
│   │       ├── formatters.ts
│   │       └── validators.ts
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── tailwind.config.ts
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── s3.tf
│   ├── iam.tf
│   ├── README.md
│   └── examples/
│       └── terraform.tfvars.example
├── docker-compose.yml                 # Production setup
├── docker-compose.dev.yml             # Development setup
├── .env.example
├── Makefile                           # Helper commands
├── README.md
├── FEATURES.md
├── ARCHITECTURE.md
├── CONTRIBUTING.md
└── LICENSE
```

---

## Configuration Management

### Environment Variables

```bash
# Application
APP_NAME=HSA Tracker
APP_ENV=production  # or development
DEBUG=false
SECRET_KEY=<generated-secret-key>
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_TYPE=postgresql  # or sqlite
DATABASE_URL=postgresql://user:pass@db:5432/hsatracker
# For SQLite: DATABASE_URL=sqlite:///./data/hsatracker.db

# AWS S3
AWS_ACCESS_KEY_ID=<from-terraform-output>
AWS_SECRET_ACCESS_KEY=<from-terraform-output>
AWS_S3_BUCKET=<from-terraform-output>
AWS_S3_REGION=us-east-1

# Auth
JWT_SECRET_KEY=<generated-secret-key>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
WEBAUTHN_RP_ID=localhost  # Your domain
WEBAUTHN_RP_NAME=HSA Tracker
WEBAUTHN_ORIGIN=http://localhost:3000

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:80

# File Upload
MAX_UPLOAD_SIZE_MB=10
ALLOWED_MIME_TYPES=image/jpeg,image/png,image/heic,application/pdf
```

---

## Deployment Guide

### Quick Start (Development)

```bash
# 1. Clone repository
git clone https://github.com/yourusername/hsa-tracker.git
cd hsa-tracker

# 2. Set up AWS infrastructure (one-time)
cd terraform
cp examples/terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your preferences
terraform init
terraform apply
# Save outputs to .env file

# 3. Configure environment
cd ..
cp .env.example .env
# Edit .env with Terraform outputs

# 4. Start application
make dev-up
# Or: docker-compose -f docker-compose.dev.yml up

# 5. Access application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Production Deployment

```bash
# 1. Set up AWS infrastructure (same as above)

# 2. Configure environment for production
cp .env.example .env
# Edit .env with production settings

# 3. Build and start
make prod-up
# Or: docker-compose up -d

# 4. Set up reverse proxy (nginx/Traefik) for SSL
# 5. Configure domain DNS
# 6. Set up backups for database and .env file
```

### Makefile Commands

```makefile
# Development
dev-up:           # Start dev environment
dev-down:         # Stop dev environment
dev-logs:         # View logs
dev-shell-backend: # Backend shell
dev-shell-frontend: # Frontend shell

# Production
prod-up:          # Start production
prod-down:        # Stop production
prod-logs:        # View logs

# Database
db-migrate:       # Run migrations
db-upgrade:       # Upgrade to latest
db-downgrade:     # Downgrade one version
db-reset:         # Reset database (destructive!)

# Testing
test-backend:     # Run backend tests
test-frontend:    # Run frontend tests
test-all:         # Run all tests

# Terraform
tf-init:          # Initialize Terraform
tf-plan:          # Plan infrastructure
tf-apply:         # Apply infrastructure
tf-destroy:       # Destroy infrastructure (careful!)

# Utilities
clean:            # Clean build artifacts
format:           # Format code (black, prettier)
lint:             # Lint code
```

---

## UI Customization System

### Custom CSS

Users can override default styles by mounting a custom CSS file:

```yaml
# docker-compose.override.yml
services:
  frontend:
    volumes:
      - ./custom-theme.css:/app/src/styles/custom-theme.css
```

### CSS Custom Properties (Variables)

```css
/* custom-theme.css */
:root {
  /* Colors */
  --color-primary: #3b82f6;
  --color-secondary: #64748b;
  --color-success: #10b981;
  --color-warning: #f59e0b;
  --color-danger: #ef4444;

  /* Typography */
  --font-family-base: 'Inter', sans-serif;
  --font-size-base: 16px;

  /* Spacing */
  --spacing-unit: 8px;

  /* Borders */
  --border-radius: 8px;
}
```

### Component Overrides (Future Enhancement)

```tsx
// Allow users to provide custom components
// frontend/src/overrides/ (user-mounted directory)
import CustomTransactionForm from '@overrides/TransactionForm';

// Use custom component if available, fallback to default
const TransactionFormComponent = CustomTransactionForm || DefaultTransactionForm;
```

---

## Future: Databricks Integration

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  HSA Tracker Backend                                         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Databricks Service (optional module)                  │ │
│  │  - Export transactions to Databricks SQL              │ │
│  │  - Trigger analytics pipelines                        │ │
│  │  - Import enriched data back                          │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  │ Databricks REST API
                  │
┌─────────────────▼───────────────────────────────────────────┐
│  Databricks Workspace (User's Account)                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Delta Tables                                          │ │
│  │  - transactions                                        │ │
│  │  - family_members                                      │ │
│  │  - categories                                          │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  SQL Warehouses                                        │ │
│  │  - Analytics queries                                   │ │
│  │  - Aggregations                                        │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Notebooks (included in repo)                          │ │
│  │  - Spending analysis                                   │ │
│  │  - Trend predictions                                   │ │
│  │  - Category recommendations                            │ │
│  │  - Tax optimization                                    │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### Implementation Plan

1. **Environment Variable Configuration**:
   ```bash
   DATABRICKS_ENABLED=true
   DATABRICKS_HOST=<workspace-url>
   DATABRICKS_TOKEN=<access-token>
   DATABRICKS_WAREHOUSE_ID=<warehouse-id>
   ```

2. **Python SDK Integration**:
   ```python
   from databricks.sdk import WorkspaceClient

   # In backend/app/services/databricks_service.py
   class DatabricksService:
       def sync_transactions(self):
           # Export to Delta tables

       def run_analytics_notebook(self, notebook_path):
           # Trigger notebook execution

       def fetch_insights(self):
           # Retrieve analysis results
   ```

3. **Included Notebooks** (in `databricks/notebooks/`):
   - `spending_trends.py`: Time-series analysis
   - `category_optimization.py`: Suggest better categorization
   - `tax_planning.py`: Tax optimization recommendations
   - `budget_forecasting.py`: Predict future expenses

4. **Terraform for Databricks** (optional):
   ```hcl
   # terraform/databricks.tf
   resource "databricks_sql_warehouse" "hsa_tracker" {
     # Auto-provisioning
   }
   ```

---

## Security Considerations

### Authentication & Authorization
- **Passkeys**: FIDO2-compliant, phishing-resistant
- **TOTP**: RFC 6238-compliant, works offline
- **JWT Tokens**: Short-lived access tokens (30 min), longer refresh tokens (7 days)
- **Session Management**: Secure HTTP-only cookies, CSRF protection
- **Rate Limiting**: Prevent brute force attacks on auth endpoints

### Data Protection
- **Encryption at Rest**:
  - Database: Encrypted volumes
  - S3: Server-side encryption (SSE-S3 or SSE-KMS)
  - Secrets: Environment variables, never committed to git
- **Encryption in Transit**: TLS 1.3 for all connections
- **Input Validation**: Pydantic schemas, SQL injection prevention (ORM)
- **XSS Prevention**: React's built-in escaping, CSP headers

### AWS Security
- **IAM**: Minimal permissions (principle of least privilege)
- **S3 Bucket**:
  - Private (no public access)
  - Block public ACLs
  - Encryption enforced
  - Versioning for recovery
  - CORS properly configured
- **Pre-signed URLs**: Time-limited (15 min), scoped to specific objects

### Multi-Tenancy Isolation
- **Row-Level Security**: All queries filtered by `family_id`
- **Database Views**: Expose only authorized data
- **API Middleware**: Verify family membership on every request
- **Audit Logging**: Track all data access

---

## Testing Strategy

### Backend Tests
- **Unit Tests**: All services and utilities (pytest)
- **Integration Tests**: API endpoints with test database
- **Auth Tests**: WebAuthn flows, TOTP verification
- **S3 Tests**: Mock boto3 with moto library
- **Coverage Goal**: >80%

### Frontend Tests
- **Component Tests**: React Testing Library
- **Integration Tests**: User flows (Playwright/Cypress)
- **Accessibility Tests**: axe-core
- **Coverage Goal**: >70%

### E2E Tests
- **Critical Paths**:
  - User registration → Setup passkey → Add transaction → Upload receipt
  - Multi-family member workflow
  - Report generation

---

## Performance Considerations

### Backend
- **Async I/O**: FastAPI with uvicorn for concurrent requests
- **Database Connection Pooling**: SQLAlchemy pool size tuning
- **Caching**: Redis for frequently accessed data (future)
- **Query Optimization**: Proper indexes, eager loading
- **Background Jobs**: Celery for async tasks (future)

### Frontend
- **Code Splitting**: Lazy load routes
- **Image Optimization**: Compress uploads, generate thumbnails
- **Pagination**: Virtualized lists for large datasets
- **Debouncing**: Search and filter inputs
- **Service Worker**: Offline support (PWA)

### S3
- **Multipart Uploads**: For large files
- **CloudFront CDN**: Optional for faster downloads (future)
- **Intelligent Tiering**: Cost optimization for infrequently accessed receipts

---

## Monitoring & Logging

### Application Logs
- **Structured Logging**: JSON format
- **Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Log Rotation**: Prevent disk space issues
- **ELK Stack**: Optional Elasticsearch + Kibana for log analysis

### Metrics
- **Health Checks**: `/api/v1/health` endpoint
- **Prometheus Metrics**: Request counts, latency, error rates (future)
- **Grafana Dashboards**: Visualize metrics (future)

### Alerts
- **Database Connection Failures**
- **S3 Upload Errors**
- **High Error Rates**
- **Disk Space Low**

---

## Migration Path

For users migrating from existing systems:

### CSV Import
```python
# backend/app/services/import_service.py
class ImportService:
    def import_from_csv(self, file, family_id, mapping):
        # Map CSV columns to transaction fields
        # Validate and import transactions
```

### Supported Formats
- Generic CSV (user defines column mapping)
- Mint export
- YNAB export
- QuickBooks export

---

## Documentation Plan

### User Documentation
- **README.md**: Quick start, overview
- **INSTALL.md**: Detailed installation steps
- **USER_GUIDE.md**: Feature walkthrough with screenshots
- **FAQ.md**: Common questions

### Developer Documentation
- **ARCHITECTURE.md**: This document
- **CONTRIBUTING.md**: Development setup, code standards
- **API.md**: API documentation (auto-generated from OpenAPI)
- **DATABASE.md**: Schema documentation

### Video Tutorials (Future)
- Initial setup walkthrough
- Adding your first expense
- Receipt management
- Custom CSS themes

---

## Roadmap

### Phase 1: MVP (Months 1-2)
- [x] Architecture design
- [ ] Backend scaffolding (FastAPI + SQLAlchemy)
- [ ] Frontend scaffolding (React + TypeScript)
- [ ] Docker setup
- [ ] Terraform AWS module
- [ ] Basic auth (passkey + TOTP)
- [ ] Transaction CRUD
- [ ] Receipt upload to S3
- [ ] Simple dashboard
- [ ] Basic reports

### Phase 2: Enhanced Features (Months 3-4)
- [ ] Family member management
- [ ] Multiple HSA accounts
- [ ] Reimbursement tracking
- [ ] Advanced filtering
- [ ] CSV import/export
- [ ] Tax year summaries
- [ ] Mobile responsive improvements

### Phase 3: Analytics & Integrations (Months 5-6)
- [ ] Databricks integration
- [ ] Advanced visualizations
- [ ] Spending predictions
- [ ] Budget planning
- [ ] OCR for receipts (optional)
- [ ] Bank import (Plaid, optional)

### Phase 4: Polish & Extensions (Months 7+)
- [ ] Native mobile apps (React Native)
- [ ] Component override system
- [ ] Plugin architecture
- [ ] Multi-language support
- [ ] Accessibility improvements (WCAG 2.1 AA)

---

## Success Metrics

- **Setup Time**: < 15 minutes from clone to running app
- **First Transaction**: < 2 minutes after login
- **Receipt Upload**: < 30 seconds per receipt
- **Page Load**: < 2 seconds for dashboard
- **API Response**: < 200ms for most endpoints
- **Test Coverage**: >80% backend, >70% frontend
- **Documentation**: All features documented

---

## Conclusion

This architecture provides a solid foundation for a self-hosted, family-friendly HSA tracker that prioritizes:

1. **Ease of deployment**: Docker + docker-compose + make commands
2. **Security**: Modern auth, AWS best practices via Terraform
3. **Extensibility**: Custom CSS, future component overrides, Databricks integration
4. **Compliance**: Built-in HSA/IRS knowledge
5. **Privacy**: Self-hosted, user owns all data and infrastructure

The modular design allows for incremental development, starting with core expense tracking and progressively adding advanced features based on user needs.
