# HSA Tracker

A self-hosted application for tracking HSA-eligible expenses, managing receipts, and monitoring HSA investments — built for families.

![Status](https://img.shields.io/badge/status-alpha-orange)
![License](https://img.shields.io/badge/license-PolyForm%20Noncommercial-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![React](https://img.shields.io/badge/react-18+-61DAFB)

## Overview

HSA Tracker connects to your bank via [Teller.io](https://teller.io), automatically surfaces potential HSA-eligible transactions, and helps you build a paper trail for tax time. Your financial data stays in your own infrastructure — S3 for receipts, PostgreSQL for records, and your own AWS account for compute.

## Screenshots

| Dashboard | Transactions | Portfolio |
|-----------|-------------|-----------|
| ![Dashboard](docs/screenshots/dashboard.png) | ![Transactions](docs/screenshots/transactions.png) | ![Portfolio](docs/screenshots/portfolio.png) |

| Bank Accounts | Family Members | Rules Engine |
|---------------|----------------|--------------|
| ![Bank](docs/screenshots/bank.png) | ![Family](docs/screenshots/family.png) | ![Rules](docs/screenshots/rules.png) |

## Features

### Expense Tracking
- Automatic bank sync via Teller.io (transactions pulled directly from your bank)
- Manual transaction entry for cash or non-linked accounts
- Tag transactions as HSA-eligible, ineligible, or pending review
- Assign transactions to family members and expense categories
- Review queue for unreviewed potential HSA expenses

### Receipt & Document Management
- Upload receipts and EOBs directly to your S3 bucket
- Attach multiple documents to a single transaction
- CVS pharmacy import (parse prescription fill history)
- Bulk CSV receipt import

### HSA Rules Engine
- Build rules to automatically flag transactions as HSA-eligible (e.g. "any transaction at CVS over $10")
- Conditions: merchant name, category, amount, description patterns
- Rule preview before applying
- Reorderable priority queue

### Investment Portfolio Tracker
- Manually track HSA investment accounts across multiple institutions
- Live price updates via Finnhub (free tier, no credit card)
- Portfolio history chart and projected growth
- Holdings snapshots for charting over time

### Family Support
- Add family members with HSA eligibility periods
- Track which transactions are for which family member
- Invite family members to share a household
- Role-based access control

### Authentication
- Passkey / WebAuthn (phishing-resistant, no password required)
- Email + password with TOTP 2FA
- Backup codes for account recovery
- Rate limiting and account lockout

### Progressive Web App
- Install to home screen on iOS and Android
- Mobile-first UI with native-feeling navigation
- Web Push notifications for HSA review reminders

## Quick Start

### Prerequisites

- **Docker Desktop** — [Download](https://www.docker.com/products/docker-desktop)
- **AWS Account** — [Sign up](https://aws.amazon.com) (free tier covers S3)
- **Teller.io Account** — [Sign up](https://teller.io) (for bank sync; optional)
- **Doppler** (optional but recommended) — [Sign up](https://www.doppler.com)

### Setup

```bash
git clone https://github.com/JEinOKC/hsa-tracker.git
cd hsa-tracker
make setup-wizard
```

The wizard checks prerequisites, configures secrets (Doppler or `.env`), provisions your S3 bucket via Terraform, and starts the app.

**Time to complete:** ~10 minutes on first run.

### Daily use

```bash
make dev-up     # Start the dev environment
make dev-down   # Stop it
make dev-logs   # Tail logs
make help       # All available commands
```

Once running:
- Frontend: `http://localhost:3001`
- Backend API: `http://localhost:8001`
- API docs (dev only): `http://localhost:8001/docs`

## Architecture

### Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS |
| Backend | Python 3.11 + FastAPI + SQLAlchemy |
| Database | PostgreSQL 16 (Neon in production) |
| Storage | AWS S3 |
| Auth | WebAuthn + JWT (PyJWT) + TOTP |
| Bank sync | Teller.io |
| Stock prices | Finnhub |

### Production Deployment

The production stack runs serverless on AWS + Cloudflare:

```
Browser → Cloudflare Pages (frontend)
              ↓
        API Gateway (HTTP API v2)
              ↓
        AWS Lambda (FastAPI via Mangum)
              ↓
        Neon PostgreSQL + AWS S3
```

Terraform manages all infrastructure. See [terraform/README.md](./terraform/README.md).

### Project Structure

```
hsa-tracker/
├── backend/                # FastAPI application
│   ├── app/
│   │   ├── api/v1/        # API endpoints
│   │   ├── models/        # SQLAlchemy models (27 models)
│   │   ├── schemas/       # Pydantic schemas
│   │   └── services/      # Business logic, rules engine
│   ├── alembic/           # Database migrations
│   ├── Dockerfile.lambda  # Lambda container image
│   └── requirements.txt
├── frontend/               # React application
│   ├── src/
│   │   ├── pages/         # 12 page components
│   │   ├── components/    # Shared UI components
│   │   └── services/      # API client layer
│   └── vite.config.ts
├── terraform/              # AWS + Cloudflare infrastructure
├── docker-compose.yml      # Production (self-hosted)
├── docker-compose.dev.yml  # Development
└── Makefile               # Build and deploy commands
```

## Configuration

Copy `.env.example` to `.env` and fill in your values:

```bash
# Database
DATABASE_URL=postgresql://user:pass@db:5432/hsatracker

# AWS S3
AWS_S3_BUCKET=your-bucket-name
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# Auth
SECRET_KEY=generate-with-openssl-rand-hex-32
JWT_SECRET_KEY=generate-with-openssl-rand-hex-32
WEBAUTHN_RP_ID=localhost        # your domain in production
WEBAUTHN_ORIGIN=http://localhost:3001

# Bank sync (optional)
TELLER_APP_ID=your-app-id

# Stock prices (optional)
PRICE_PROVIDER=finnhub
FINNHUB_API_KEY=your-key        # free at finnhub.io
```

See [.env.example](./.env.example) for all options.

### Stock price providers

Finnhub is the default and recommended provider — free tier covers 60 calls/minute with no expiry. To add a new provider, implement the `PriceProvider` protocol in `backend/app/services/price_fetcher.py` and register it in the `PROVIDERS` dict.

### UI themes

Override CSS variables in `frontend/src/styles/custom-theme.css`:

```css
:root {
  --color-primary: #9333ea;
  --font-family-base: 'Inter', sans-serif;
}
```

## Development

```bash
make dev-up          # Start all services with hot reload
make test-backend    # Run backend tests (pytest)
make test-frontend   # Run frontend tests (vitest)
make test-all        # Run all tests
make audit           # Check dependencies for CVEs
make format          # Format code (ruff + prettier)
make lint            # Lint (ruff + eslint)
make db-migrate      # Create a new migration
make db-upgrade      # Apply pending migrations
```

## Deployment

### Serverless (recommended)

The app deploys to AWS Lambda + Cloudflare Pages via Terraform and `make deploy`.

```bash
make tf-apply          # Provision AWS + Cloudflare infrastructure
make deploy            # Build Lambda image, run migrations, deploy frontend
```

See [terraform/README.md](./terraform/README.md) for first-time setup.

### Self-hosted (Docker)

```bash
# Copy and edit your production env
cp .env.example .env

# Start the stack
make prod-up
```

Set up a reverse proxy (nginx/Traefik) for SSL in front of port 3001.

### Database backup

```bash
docker-compose exec db pg_dump -U hsatracker hsatracker > backup.sql
docker-compose exec -T db psql -U hsatracker hsatracker < backup.sql
```

## Roadmap

### Shipped
- [x] Bank sync via Teller.io (transactions, accounts, connection health)
- [x] Manual transaction entry
- [x] HSA eligibility tagging and review queue
- [x] HSA rules engine (auto-flag transactions by merchant, category, amount)
- [x] Receipt upload to S3
- [x] CVS pharmacy import
- [x] Bulk CSV receipt import
- [x] Family member management with eligibility periods
- [x] Multi-user households with roles and access control
- [x] Investment portfolio tracker (manual holdings, live prices, history)
- [x] Dashboard with sparkline chart
- [x] Passkey (WebAuthn) + TOTP 2FA + backup codes
- [x] Progressive Web App (installable, push notifications)
- [x] AWS Lambda + Cloudflare Pages deployment via Terraform

### Planned
- [ ] Tax year summary export (Form 8889 data prep)
- [ ] CSV export for transactions
- [ ] Budget planning and annual contribution tracker
- [ ] OCR for receipt scanning
- [ ] Native mobile apps (currently PWA)

## Contributing

1. Fork the repository
2. Clone your fork
3. Run `make setup-wizard`
4. Create a feature branch (`git checkout -b feature/my-feature`)
5. Make your changes with tests (`make test-all`)
6. Submit a pull request

See [CONTRIBUTING.md](./CONTRIBUTING.md) for development guidelines.

## License

PolyForm Noncommercial License 1.0.0 — free for personal use, not for commercial use. See [LICENSE](./LICENSE) for details.

## Disclaimer

This software is for personal organizational use only. It is not a substitute for professional tax or financial advice. Consult a qualified professional for HSA eligibility determinations and tax filing.
