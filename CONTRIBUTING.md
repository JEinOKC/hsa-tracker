# Contributing to HSA Tracker

Thank you for your interest in contributing to HSA Tracker! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Project Structure](#project-structure)

## Code of Conduct

We are committed to providing a welcoming and inclusive environment for all contributors. Please:

- Be respectful and constructive in communication
- Welcome newcomers and help them get started
- Focus on what is best for the community
- Show empathy towards other community members

## Getting Started

### Prerequisites

- Git
- Docker & Docker Compose
- Python 3.11+ (for local development)
- Node.js 20+ (for local development)
- AWS Account (for testing S3 features)
- Terraform (for infrastructure testing)

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/hsa-tracker.git
   cd hsa-tracker
   ```
3. Add the upstream repository:
   ```bash
   git remote add upstream https://github.com/original/hsa-tracker.git
   ```

## Development Setup

### 1. Initial Configuration

```bash
# Create environment files
make setup

# Edit .env with your configuration
nano .env
```

### 2. Set Up AWS Infrastructure (Optional)

If you're working on S3-related features:

```bash
# Configure Terraform
cd terraform
cp examples/terraform.tfvars.example terraform.tfvars
nano terraform.tfvars

# Create AWS resources
make tf-init
make tf-apply
```

### 3. Start Development Environment

```bash
# Start all services with hot-reload
make dev-up

# View logs
make dev-logs
```

### 4. Access Services

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Database: localhost:5432

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

Branch naming conventions:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation changes
- `refactor/` - Code refactoring
- `test/` - Test additions or modifications

### 2. Make Changes

#### Backend Development

The backend is in `backend/` and uses FastAPI.

```bash
# Install dependencies locally (optional)
cd backend
pip install -r requirements.txt -r requirements-dev.txt

# Access backend container shell
make dev-shell-backend

# Run migrations
make db-upgrade

# Create a new migration
make db-migrate
```

**Backend Code Structure:**
- `app/api/v1/endpoints/` - API route handlers
- `app/models/` - SQLAlchemy database models
- `app/schemas/` - Pydantic validation schemas
- `app/services/` - Business logic
- `app/utils/` - Utility functions

#### Frontend Development

The frontend is in `frontend/` and uses React + TypeScript.

```bash
# Install dependencies locally (optional)
cd frontend
npm install

# Access frontend container shell
make dev-shell-frontend

# Build for production
npm run build
```

**Frontend Code Structure:**
- `src/pages/` - Route pages
- `src/components/` - Reusable components
- `src/hooks/` - Custom React hooks
- `src/services/` - API clients
- `src/styles/` - CSS and themes

### 3. Test Your Changes

```bash
# Run all tests
make test-all

# Run backend tests only
make test-backend

# Run frontend tests only
make test-frontend

# Check code formatting
make lint
```

### 4. Commit Your Changes

Follow conventional commit format:

```bash
git commit -m "type(scope): description

Longer explanation if needed

Fixes #123"
```

**Commit types:**
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation changes
- `style` - Code style changes (formatting, etc.)
- `refactor` - Code refactoring
- `test` - Test additions or changes
- `chore` - Build process or auxiliary tool changes

**Examples:**
```bash
git commit -m "feat(transactions): add CSV export functionality"
git commit -m "fix(auth): resolve passkey registration error"
git commit -m "docs(readme): update installation instructions"
```

### 5. Push and Create Pull Request

```bash
# Push to your fork
git push origin feature/your-feature-name
```

Then create a pull request on GitHub.

## Code Standards

### Python (Backend)

We use:
- **Black** for code formatting
- **Flake8** for linting
- **isort** for import sorting
- **mypy** for type checking (optional)

```bash
# Format code
docker-compose -f docker-compose.dev.yml exec backend black app/

# Lint code
docker-compose -f docker-compose.dev.yml exec backend flake8 app/

# Sort imports
docker-compose -f docker-compose.dev.yml exec backend isort app/
```

**Guidelines:**
- Maximum line length: 100 characters
- Use type hints for function signatures
- Write docstrings for all public functions
- Follow PEP 8 style guide

**Example:**
```python
from typing import List, Optional
from pydantic import BaseModel


def get_transactions(
    family_id: str,
    limit: int = 100,
    offset: int = 0
) -> List[Transaction]:
    """
    Retrieve transactions for a family.

    Args:
        family_id: The family identifier
        limit: Maximum number of results
        offset: Number of records to skip

    Returns:
        List of transaction objects
    """
    # Implementation
    pass
```

### TypeScript (Frontend)

We use:
- **Prettier** for code formatting
- **ESLint** for linting

```bash
# Format code
docker-compose -f docker-compose.dev.yml exec frontend npm run format

# Lint code
docker-compose -f docker-compose.dev.yml exec frontend npm run lint
```

**Guidelines:**
- Use functional components with hooks
- Use TypeScript for all new code
- Avoid `any` types when possible
- Use meaningful variable names

**Example:**
```typescript
import { useState, useEffect } from 'react'
import { Transaction } from '@/types/models'

interface TransactionListProps {
  familyId: string
  onSelect?: (transaction: Transaction) => void
}

export function TransactionList({ familyId, onSelect }: TransactionListProps) {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Fetch transactions
  }, [familyId])

  return (
    // JSX
  )
}
```

## Testing

### Backend Tests

Tests are in `backend/tests/` using pytest.

```bash
# Run all backend tests
make test-backend

# Run specific test file
docker-compose -f docker-compose.dev.yml exec backend pytest tests/test_auth.py

# Run with coverage
docker-compose -f docker-compose.dev.yml exec backend pytest --cov=app
```

**Test Structure:**
```python
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_create_transaction(client):
    response = client.post(
        "/api/v1/transactions/",
        json={
            "amount": 50.00,
            "merchant_name": "Test Pharmacy",
            # ...
        }
    )
    assert response.status_code == 201
    assert response.json()["amount"] == 50.00
```

### Frontend Tests

Tests are in `frontend/src/` (co-located with components) using React Testing Library.

```bash
# Run all frontend tests
make test-frontend

# Run in watch mode
docker-compose -f docker-compose.dev.yml exec frontend npm test -- --watch
```

**Test Structure:**
```typescript
import { render, screen } from '@testing-library/react'
import { TransactionList } from './TransactionList'

describe('TransactionList', () => {
  it('renders empty state when no transactions', () => {
    render(<TransactionList familyId="test-family" />)
    expect(screen.getByText(/no transactions/i)).toBeInTheDocument()
  })

  it('displays transactions when loaded', async () => {
    // Test implementation
  })
})
```

### Coverage Goals

- Backend: >80% code coverage
- Frontend: >70% code coverage

## Pull Request Process

### Before Submitting

1. ✅ All tests pass (`make test-all`)
2. ✅ Code is formatted (`make format`)
3. ✅ Code passes linting (`make lint`)
4. ✅ Documentation is updated (if applicable)
5. ✅ Commit messages follow conventional format
6. ✅ Branch is up to date with `main`

### Submitting

1. Push your branch to your fork
2. Create a pull request on GitHub
3. Fill out the PR template completely
4. Link any related issues
5. Request review from maintainers

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring

## Testing
How was this tested?

## Screenshots
(If applicable)

## Checklist
- [ ] Tests pass
- [ ] Code is formatted
- [ ] Documentation updated
- [ ] Backwards compatible

## Related Issues
Fixes #123
```

### Review Process

- At least one maintainer approval required
- All CI checks must pass
- Address all review comments
- Squash commits if requested

## Project Structure

```
hsa-tracker/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/    # API routes
│   │   ├── models/              # Database models
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── services/            # Business logic
│   │   ├── utils/               # Utilities
│   │   ├── config.py            # Configuration
│   │   ├── database.py          # DB setup
│   │   └── main.py              # FastAPI app
│   ├── tests/                   # Backend tests
│   ├── requirements.txt         # Python dependencies
│   └── Dockerfile               # Backend container
├── frontend/
│   ├── src/
│   │   ├── components/          # React components
│   │   ├── pages/               # Route pages
│   │   ├── hooks/               # Custom hooks
│   │   ├── services/            # API clients
│   │   ├── styles/              # CSS
│   │   └── main.tsx             # Entry point
│   ├── package.json             # Node dependencies
│   └── Dockerfile               # Frontend container
├── terraform/                   # AWS infrastructure
├── docker-compose.yml           # Production setup
├── docker-compose.dev.yml       # Development setup
├── Makefile                     # Helper commands
├── .env.example                 # Example config
└── README.md                    # Main documentation
```

## Getting Help

- **Questions?** Open a [Discussion](https://github.com/yourusername/hsa-tracker/discussions)
- **Bug Report?** Create an [Issue](https://github.com/yourusername/hsa-tracker/issues)
- **Security Issue?** Email security@example.com (do not create public issue)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to HSA Tracker! 🎉
