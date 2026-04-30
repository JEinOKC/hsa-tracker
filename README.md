# HSA Tracker

A self-hosted solution for tracking and managing HSA-eligible spending for families.

![Status](https://img.shields.io/badge/status-alpha-orange)
![Version](https://img.shields.io/badge/version-0.1.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Overview

HSA Tracker is a self-hosted application designed to help families track Health Savings Account (HSA) eligible expenses, manage receipts, and prepare for tax reporting. Built with privacy and data ownership in mind, all your financial data stays under your control.

### Key Features

- 📊 **Expense Tracking**: Record and categorize HSA-eligible expenses
- 📸 **Receipt Management**: Upload and store receipts securely in your own AWS S3 bucket
- 👨‍👩‍👧‍👦 **Family Support**: Track expenses for multiple family members with tax dependent tracking
- 🔐 **Modern Authentication**: Passkey (WebAuthn) and TOTP 2FA support
- 📈 **Reports & Analytics**: Spending trends, tax summaries, and contribution tracking
- 💼 **Investment Portfolio Tracker**: Manually track HSA investment holdings across multiple institutions with live price updates and growth projections
- 🏠 **Self-Hosted**: Complete control over your data and infrastructure
- 🐳 **Easy Deployment**: Docker-based setup with one-command deployment
- 🔧 **Extensible**: Customizable UI themes and future Databricks integration

## Quick Start

**New to AWS or Terraform? No problem!** We have an interactive setup wizard that guides you through everything.

### Super Simple Setup (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/JEinOKC/hsa-tracker.git
cd hsa-tracker

# 2. Run the setup wizard
make setup-wizard
```

That's it! The wizard will:
- ✅ Check prerequisites and guide you to install what's missing
- ✅ Help you choose between Doppler (secure secrets) or .env files (simple)
- ✅ Guide you through creating an AWS account (if needed)
- ✅ Automatically create your S3 bucket with Terraform
- ✅ Generate all secrets and configure everything
- ✅ Start the application

**Time to complete:** 5-10 minutes (first time)

📖 **[See the complete setup guide →](./SETUP_GUIDE.md)**

### Prerequisites

- **Docker Desktop** - [Download here](https://www.docker.com/products/docker-desktop)
- **AWS Account** - [Sign up here](https://aws.amazon.com) (free tier available)
- **Doppler Account** (optional but recommended) - [Sign up here](https://www.doppler.com)

Everything else is optional - the wizard will guide you!

### After Setup

```bash
# Access the application
open http://localhost:3000

# Create your first user
# Click "Create one" → Fill in the form → Start tracking!
```

**Daily use:**
```bash
make dev-up    # Start the app
make dev-down  # Stop the app
make dev-logs  # View logs
make help      # See all commands
```

## Architecture

### Technology Stack

- **Backend**: Python 3.11+ with FastAPI
- **Frontend**: React 18+ with TypeScript
- **Database**: PostgreSQL 16 (or SQLite for simple deployments)
- **Storage**: AWS S3 (self-managed bucket)
- **Deployment**: Docker & Docker Compose
- **Infrastructure**: Terraform for AWS provisioning

### Project Structure

```
hsa-tracker/
├── backend/              # FastAPI backend application
├── frontend/             # React frontend application
├── terraform/            # AWS infrastructure as code
├── docker-compose.yml    # Production setup
├── docker-compose.dev.yml # Development setup
├── Makefile              # Helper commands
└── .env                  # Configuration (create from .env.example)
```

## Documentation

- [Installation Guide](./INSTALL.md) - Detailed installation instructions
- [Architecture](./ARCHITECTURE.md) - Technical architecture and design decisions
- [Features](./FEATURES.md) - Complete feature requirements and roadmap
- [Contributing](./CONTRIBUTING.md) - Development setup and contribution guidelines
- [Terraform Setup](./terraform/README.md) - AWS infrastructure setup

## Development

### Start Development Environment

```bash
make dev-up
```

This starts all services with hot-reloading enabled:
- Frontend dev server (Vite) on port 3000
- Backend dev server (uvicorn with reload) on port 8000
- PostgreSQL database on port 5432

### Useful Commands

```bash
make help                # Show all available commands
make dev-logs           # View development logs
make db-migrate         # Create a new database migration
make db-upgrade         # Apply database migrations
make test-all           # Run all tests
make format             # Format code (black + prettier)
make lint               # Lint code (flake8 + eslint)
```

### Running Tests

```bash
# Backend tests
make test-backend

# Frontend tests
make test-frontend

# All tests
make test-all
```

## Configuration

### Environment Variables

Key configuration options in `.env`:

```bash
# Database
DATABASE_TYPE=postgresql
DATABASE_URL=postgresql://user:pass@db:5432/hsatracker

# AWS S3 (from Terraform outputs)
AWS_S3_BUCKET=your-bucket-name
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# Authentication
JWT_SECRET_KEY=your-secret-key
WEBAUTHN_RP_ID=localhost  # Your domain in production

# HSA Portfolio — stock price fetching (optional)
PRICE_PROVIDER=finnhub       # or alphavantage (default: finnhub)
FINNHUB_API_KEY=             # required when PRICE_PROVIDER=finnhub
```

See [.env.example](./.env.example) for all available options.

### HSA Portfolio price fetching

The portfolio tracker can fetch live stock prices to keep your holding values up to date. This is optional — holdings without prices still display with shares and a manual value entry.

**Finnhub** (default, recommended):
1. Sign up for a free account at [finnhub.io](https://finnhub.io) — no credit card required
2. Copy your API key from the dashboard
3. Add `FINNHUB_API_KEY=your_key_here` to your `.env` file
4. Free tier: 60 API calls/minute, no expiry

The provider is configurable via `PRICE_PROVIDER` env var. To add a new provider, implement the `PriceProvider` protocol in `backend/app/services/price_fetcher.py` and register it in the `PROVIDERS` dict — no other code changes needed.

### UI Customization

Customize the UI by overriding CSS variables in `frontend/src/styles/custom-theme.css`:

```css
:root {
  --color-primary: #9333ea;
  --font-family-base: 'Roboto', sans-serif;
}
```

## Deployment

### Production Deployment

1. Update `.env` with production settings:
   - Set `APP_ENV=production`
   - Set `DEBUG=false`
   - Generate strong secrets for `SECRET_KEY` and `JWT_SECRET_KEY`
   - Update `WEBAUTHN_RP_ID` and `WEBAUTHN_ORIGIN` to your domain

2. Start production containers:
   ```bash
   make prod-up
   ```

3. Set up a reverse proxy (nginx/Traefik) for SSL termination

4. Configure DNS to point to your server

### Backup & Restore

**Database Backup:**
```bash
docker-compose exec db pg_dump -U hsatracker hsatracker > backup.sql
```

**Database Restore:**
```bash
docker-compose exec -T db psql -U hsatracker hsatracker < backup.sql
```

**Receipts Backup:**
Your receipts are stored in AWS S3 with versioning enabled. Enable cross-region replication for additional redundancy.

## Security Considerations

- All data stored in your own AWS account and self-hosted infrastructure
- Passkey authentication (FIDO2-compliant, phishing-resistant)
- TOTP 2FA support (works offline with authenticator apps)
- S3 bucket is private with encryption at rest
- No third-party data sharing or tracking
- Regular security updates recommended

## Roadmap

### MVP (v0.1.0) - Current
- [x] Basic expense tracking
- [x] Receipt upload to S3
- [x] Family member management
- [x] Simple dashboard
- [ ] Authentication implementation (passkey + TOTP)
- [ ] Database models and migrations

### v0.2.0 - Enhanced Features
- [ ] Advanced filtering and search
- [ ] CSV import/export
- [ ] Tax year summaries (Form 8889 data prep)
- [ ] Reimbursement tracking
- [ ] Multiple HSA accounts

### v0.3.0 - Analytics
- [ ] Spending trends and visualizations
- [ ] Budget planning
- [ ] Category recommendations
- [ ] Predictive analytics

### v0.4.0 - Integrations
- [ ] Databricks integration
- [ ] OCR for receipts
- [ ] Bank import (Plaid)
- [ ] Mobile apps

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for development setup and guidelines.

### Development Setup

1. Fork the repository
2. Clone your fork
3. Run `make setup`
4. Create a feature branch
5. Make your changes
6. Run tests: `make test-all`
7. Submit a pull request

## Support

- **Issues**: [GitHub Issues](https://github.com/JEinOKC/hsa-tracker/issues)
- **Discussions**: [GitHub Discussions](https://github.com/JEinOKC/hsa-tracker/discussions)
- **Documentation**: See the `docs/` directory

## License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Frontend powered by [React](https://react.dev/)
- Infrastructure provisioning with [Terraform](https://www.terraform.io/)
- Containerization with [Docker](https://www.docker.com/)

## Disclaimer

This software is provided for informational and organizational purposes. It is not a substitute for professional tax or financial advice. Always consult with qualified professionals regarding HSA eligibility, tax reporting, and financial planning.

---

**Star this repo if you find it useful! ⭐**
