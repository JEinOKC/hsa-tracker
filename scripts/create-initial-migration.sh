#!/bin/bash
# Script to create and run initial database migration

echo "Creating initial database migration..."

# Navigate to backend directory
cd "$(dirname "$0")/../" || exit 1

# Generate migration
docker compose -f docker-compose.dev.yml exec -T backend alembic revision --autogenerate -m "Initial migration - user authentication tables"

# Run migration
docker compose -f docker-compose.dev.yml exec -T backend alembic upgrade head

echo "Migration complete!"
