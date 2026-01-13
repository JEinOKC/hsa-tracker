# Database Migration Instructions

## Overview

We've added new database models for expense tracking:
- `families` - Family/household for multi-tenant support
- `family_members` - Individual family members
- `expense_categories` - HSA expense categories (system + custom)
- `hsa_accounts` - HSA account management
- `hsa_contributions` - HSA contribution tracking
- `transactions` - Expense transactions
- `receipts` - Receipt files stored in S3

## Generate and Run Migration

To create and apply the database migration for these new tables:

```bash
# Generate a new migration
make db-migrate

# Or manually:
docker-compose -f docker-compose.dev.yml exec backend alembic revision --autogenerate -m "Add expense tracking models"

# Apply the migration
docker-compose -f docker-compose.dev.yml exec backend alembic upgrade head
```

## What Gets Created

The migration will create the following tables:

### families
- id (UUID, primary key)
- name (varchar)
- created_at (timestamp)
- updated_at (timestamp)

### family_members
- id (UUID, primary key)
- family_id (UUID, foreign key to families)
- user_id (UUID, foreign key to users, nullable)
- name (varchar)
- relationship (enum: self, spouse, child, other)
- date_of_birth (date, nullable)
- is_tax_dependent (boolean)
- is_active (boolean)
- created_at (timestamp)
- updated_at (timestamp)

### expense_categories
- id (UUID, primary key)
- family_id (UUID, foreign key to families, nullable)
- name (varchar)
- description (text, nullable)
- is_hsa_eligible (boolean)
- parent_category_id (UUID, foreign key to expense_categories, nullable)
- is_system_category (boolean)
- created_at (timestamp)

### hsa_accounts
- id (UUID, primary key)
- family_id (UUID, foreign key to families)
- account_holder_id (UUID, foreign key to family_members)
- name (varchar)
- current_balance (decimal)
- contribution_limit_type (enum: individual, family)
- created_at (timestamp)
- updated_at (timestamp)

### hsa_contributions
- id (UUID, primary key)
- hsa_account_id (UUID, foreign key to hsa_accounts)
- amount (decimal)
- contribution_date (date)
- contribution_type (enum: employee, employer, other)
- tax_year (integer)
- notes (text, nullable)
- created_at (timestamp)

### transactions
- id (UUID, primary key)
- family_id (UUID, foreign key to families)
- family_member_id (UUID, foreign key to family_members)
- category_id (UUID, foreign key to expense_categories)
- hsa_account_id (UUID, foreign key to hsa_accounts, nullable)
- transaction_date (date)
- amount (decimal)
- merchant_name (varchar, nullable)
- description (text, nullable)
- payment_method (enum: hsa_card, personal, other)
- reimbursement_status (enum: not_needed, pending, reimbursed, not_seeking)
- reimbursed_date (date, nullable)
- tax_year (integer)
- created_by_user_id (UUID, foreign key to users, nullable)
- created_at (timestamp)
- updated_at (timestamp)

### receipts
- id (UUID, primary key)
- transaction_id (UUID, foreign key to transactions)
- file_name (varchar)
- file_size (integer)
- mime_type (varchar)
- s3_key (varchar, unique)
- s3_bucket (varchar)
- thumbnail_s3_key (varchar, nullable)
- upload_date (timestamp)
- uploaded_by_user_id (UUID, foreign key to users, nullable)
- created_at (timestamp)

## Automatic Behaviors

After running the migration and restarting the backend:

1. **Default Categories Seeded**: On app startup, 26 default HSA-eligible expense categories will be automatically seeded (if not already present)

2. **Auto-Family Creation**: When a new user registers with passkey authentication, a family and family member record are automatically created for them

## Verify Migration

After running the migration, you can verify it worked by:

1. Check the database tables:
```bash
docker-compose -f docker-compose.dev.yml exec db psql -U postgres -d hsatracker -c "\dt"
```

2. Check the backend logs for the category seeding message:
```bash
docker-compose -f docker-compose.dev.yml logs backend | grep "expense categories"
```

3. Test the API endpoints:
   - GET /api/v1/categories - Should return 26 default categories
   - GET /api/v1/transactions - Should work (even if empty)

## Troubleshooting

If migration fails:
- Check backend logs: `docker-compose -f docker-compose.dev.yml logs backend`
- Verify all models are imported in `backend/app/models/__init__.py`
- Ensure database is running: `docker-compose -f docker-compose.dev.yml ps`
- Check for database connection errors in the logs

If you need to reset the database (WARNING: destroys all data):
```bash
make db-reset
```
