# Creating the Authentication Database Migration

The authentication models are defined but the database tables haven't been created yet. Follow these steps to generate and apply the migration.

## Prerequisites

- Docker and Docker Compose running
- `.env` file configured with database settings

## Step-by-Step Instructions

### 1. Start the Database

```bash
# From the project root
make dev-up
```

This will start all containers, including the PostgreSQL database.

### 2. Generate the Migration

```bash
# Create a migration file
docker-compose -f docker-compose.dev.yml exec backend alembic revision --autogenerate -m "Add user authentication tables"
```

This command:
- Connects to the database
- Compares the database schema with your SQLAlchemy models
- Generates a migration file in `backend/app/db/migrations/versions/`

### 3. Review the Migration

```bash
# Find the migration file
ls -la backend/app/db/migrations/versions/
```

Open the migration file and review it. It should include:
- `users` table with columns: id, email, hashed_password, display_name, is_active, is_superuser, created_at, updated_at
- `user_passkeys` table
- `user_totp` table
- `user_backup_codes` table

### 4. Apply the Migration

```bash
# Apply the migration to create tables
docker-compose -f docker-compose.dev.yml exec backend alembic upgrade head
```

Or simply:
```bash
make db-upgrade
```

### 5. Verify Tables Were Created

```bash
# Connect to the database
docker-compose -f docker-compose.dev.yml exec db psql -U hsatracker -d hsatracker

# List tables
\dt

# Describe users table
\d users

# Exit psql
\q
```

You should see tables:
- `users`
- `user_passkeys`
- `user_totp`
- `user_backup_codes`
- `alembic_version` (migration tracking)

## Troubleshooting

### "No module named app"

If you get this error, the Python package isn't installed in the container:

```bash
# Rebuild the backend container
docker-compose -f docker-compose.dev.yml build backend
docker-compose -f docker-compose.dev.yml up -d backend
```

### "Target database is not up to date"

This means there are unapplied migrations:

```bash
# Check migration status
docker-compose -f docker-compose.dev.yml exec backend alembic current
docker-compose -f docker-compose.dev.yml exec backend alembic history

# Apply all migrations
make db-upgrade
```

### "Did not auto-generate any changes"

The models are already in sync with the database. Check if tables already exist:

```bash
docker-compose -f docker-compose.dev.yml exec db psql -U hsatracker -d hsatracker -c "\dt"
```

### Database Connection Errors

Ensure the database is running and healthy:

```bash
# Check container status
docker-compose -f docker-compose.dev.yml ps

# Check database logs
docker-compose -f docker-compose.dev.yml logs db

# Restart database
docker-compose -f docker-compose.dev.yml restart db
```

## After Migration Success

Once the migration is applied, you can:

1. **Test user registration**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/register \
     -H "Content-Type: application/json" \
     -d '{
       "email": "admin@example.com",
       "password": "SecurePassword123!",
       "display_name": "Admin User"
     }'
   ```

2. **Test login**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{
       "email": "admin@example.com",
       "password": "SecurePassword123!"
     }'
   ```

3. **Test protected endpoint**:
   ```bash
   # Save the access_token from login response
   TOKEN="eyJ..."

   curl -X GET http://localhost:8000/api/v1/auth/me \
     -H "Authorization: Bearer $TOKEN"
   ```

## Clean Start (If Needed)

If you want to start completely fresh:

```bash
# Stop containers and remove volumes
make dev-down
docker-compose -f docker-compose.dev.yml down -v

# Start fresh
make dev-up

# Create migration
# (Follow steps 2-4 above)
```

## Using Makefile Commands

For convenience, you can use these Makefile commands:

```bash
make db-migrate       # Create a new migration (will prompt for name)
make db-upgrade       # Apply all pending migrations
make db-downgrade     # Rollback one migration
make db-reset         # Reset database (WARNING: deletes all data!)
```

## Next Steps

After the migration is successful:

1. ✅ Backend authentication is fully functional
2. ⏳ Implement frontend auth components
3. ⏳ Update existing endpoints to require authentication
4. ⏳ Test the complete auth flow end-to-end
