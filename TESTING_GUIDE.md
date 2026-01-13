# Expense Tracking - Testing Guide

## Overview

This guide will help you test the complete expense tracking feature that has been implemented. The system now includes:

- ✅ Backend API endpoints for transactions, categories, and receipts
- ✅ Database models for families, members, expenses, and receipts
- ✅ Frontend UI for adding and viewing expenses
- ✅ Auto-family creation on user registration
- ✅ 26 default HSA-eligible expense categories
- ✅ S3 integration for receipt uploads

## Prerequisites

Before testing, ensure you have:

1. ✅ All code changes committed and pushed (already done)
2. ⚠️ **Database migration needs to be run** - See step 1 below
3. ⚠️ Docker containers running
4. ⚠️ AWS S3 credentials configured in .env

## Step 1: Run Database Migration

**CRITICAL**: You must run the database migration first to create the new tables.

```bash
# Start dev environment if not running
make dev-up

# Generate and run migration
make db-migrate

# Or manually:
docker-compose -f docker-compose.dev.yml exec backend alembic revision --autogenerate -m "Add expense tracking models"
docker-compose -f docker-compose.dev.yml exec backend alembic upgrade head

# Restart backend to seed categories
docker-compose -f docker-compose.dev.yml restart backend
```

### Verify Migration Success

Check backend logs for category seeding:
```bash
docker-compose -f docker-compose.dev.yml logs backend | grep "expense categories"
```

You should see:
```
Checking default expense categories...
Seeded 26 default expense categories
```

If you see "System categories already exist", that's fine - it means categories were already seeded.

## Step 2: Test User Registration Flow

### Test Auto-Family Creation

1. **If you already have a user**:
   - You may need to manually add a family and family member to the database
   - OR create a new test user to verify the auto-creation

2. **Create a new test user** (recommended):
   ```
   Navigate to: http://localhost:3001/register

   - Enter username: testuser2
   - Enter display name: Test User Two
   - Click "Create Account with Passkey"
   - Complete biometric authentication
   ```

3. **Verify family was auto-created**:
   ```bash
   docker-compose -f docker-compose.dev.yml exec db psql -U postgres -d hsatracker -c "SELECT * FROM families;"
   docker-compose -f docker-compose.dev.yml exec db psql -U postgres -d hsatracker -c "SELECT id, name, relationship FROM family_members;"
   ```

   You should see:
   - A family named "[Display Name]'s Family"
   - A family member with relationship "self"

## Step 3: Test Categories API

### List Categories

```bash
# Get access token (after login)
TOKEN="your_access_token_from_localStorage"

# List all categories
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8001/api/v1/categories

# Expected: 26 categories including:
# - Doctor Visits
# - Prescription Medications
# - Dental Care
# - Vision Care
# - etc.
```

### Test in Browser

```javascript
// Open browser console on http://localhost:3001
// Run this after logging in:

const token = localStorage.getItem('access_token')

fetch('http://localhost:8001/api/v1/categories', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
})
.then(r => r.json())
.then(data => console.log(`Found ${data.length} categories:`, data))
```

## Step 4: Test Expense Entry UI

### Navigate to Transactions Page

1. **Login**: http://localhost:3001/login
2. **Go to Transactions**: Click "Back to Dashboard" then navigate to `/transactions`
   - Or directly: http://localhost:3001/transactions

### Add Your First Expense

1. **Click "Add Expense" button**

2. **Fill out the form**:
   - Date: Select today's date (default)
   - Amount: Enter 45.99
   - Family Member: Should auto-select your name
   - Category: Select "Doctor Visits"
   - Merchant: Enter "Dr. Smith Medical Group"
   - Description: Enter "Annual checkup"
   - Payment Method: Select "Personal Card/Cash"
   - Reimbursement Status: Select "Pending Reimbursement"

3. **Click "Add Expense"**

4. **Verify**:
   - Form should clear
   - Form should hide
   - Transaction should appear in list below
   - Total amount should show $45.99

### Add Multiple Expenses

Add several different types of expenses:

```
1. Prescription:
   - Amount: $25.50
   - Category: Prescription Medications
   - Merchant: CVS Pharmacy
   - Payment: HSA Card
   - Status: Not Needed

2. Dental:
   - Amount: $150.00
   - Category: Dental Care
   - Merchant: Smile Dental
   - Payment: Personal
   - Status: Pending Reimbursement

3. Vision:
   - Amount: $200.00
   - Category: Vision Care
   - Merchant: LensCrafters
   - Payment: Personal
   - Status: Not Seeking Reimbursement
```

## Step 5: Test Transaction List Features

### Verify List Display

Check that the list shows:
- ✅ All expenses you added
- ✅ Correct dates, amounts, and categories
- ✅ Color-coded status badges:
  - Yellow for "Pending"
  - Green for "Reimbursed"
  - Gray for "Not Needed"
  - Blue for "Not Seeking"
- ✅ Total amount at bottom
- ✅ Count of expenses

### Test Delete Function

1. Click "Delete" on one expense
2. Confirm the deletion
3. Verify expense is removed from list
4. Verify total amount updates

### Test Edit Function (Note: Edit UI not implemented yet)

The "Edit" button is visible but edit functionality needs to be implemented separately.

## Step 6: Test API Endpoints Directly

### Create Transaction

```bash
TOKEN="your_access_token"

curl -X POST http://localhost:8001/api/v1/transactions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "family_member_id": "YOUR_FAMILY_MEMBER_ID",
    "category_id": "A_CATEGORY_ID",
    "transaction_date": "2026-01-13",
    "amount": 75.00,
    "merchant_name": "Test Merchant",
    "payment_method": "personal",
    "reimbursement_status": "pending"
  }'
```

### List Transactions

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8001/api/v1/transactions?limit=10"
```

### Get Single Transaction

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8001/api/v1/transactions/TRANSACTION_ID"
```

### Update Transaction

```bash
curl -X PUT http://localhost:8001/api/v1/transactions/TRANSACTION_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reimbursement_status": "reimbursed",
    "reimbursed_date": "2026-01-13"
  }'
```

### Delete Transaction

```bash
curl -X DELETE http://localhost:8001/api/v1/transactions/TRANSACTION_ID \
  -H "Authorization: Bearer $TOKEN"
```

## Step 7: Test Receipt Upload (Requires S3)

**Note**: Receipt upload requires valid AWS S3 credentials in your .env file.

### Get Upload URL

```bash
TOKEN="your_access_token"
TRANSACTION_ID="your_transaction_id"

curl -X POST "http://localhost:8001/api/v1/receipts/upload-url?transaction_id=$TRANSACTION_ID&file_name=receipt.jpg&mime_type=image/jpeg" \
  -H "Authorization: Bearer $TOKEN"
```

### Full Upload Flow (Manual Test)

1. Create a transaction (see above)
2. Get the transaction ID from response
3. Use the receipt upload endpoints to:
   - Get pre-signed URL
   - Upload file to S3
   - Create receipt record

## Known Limitations & Future Work

### Not Yet Implemented:
- ❌ Edit transaction UI (button exists but no modal)
- ❌ Receipt upload UI in frontend
- ❌ Receipt preview/download in UI
- ❌ Filtering transactions by date/category/member
- ❌ Search functionality
- ❌ Pagination (currently shows first 50)
- ❌ Export to CSV
- ❌ Dashboard with analytics
- ❌ HSA account management

### Working Features:
- ✅ Add expenses with all fields
- ✅ View list of expenses
- ✅ Delete expenses
- ✅ Auto-load categories and family members
- ✅ Status color coding
- ✅ Total calculations
- ✅ Form validation
- ✅ Error handling
- ✅ Auto-refresh after adding

## Troubleshooting

### "User is not associated with a family" Error

This means the family wasn't auto-created. Fix:

```bash
# Check if user has family member
docker-compose -f docker-compose.dev.yml exec db psql -U postgres -d hsatracker -c "SELECT * FROM family_members WHERE user_id = (SELECT id FROM users WHERE username = 'YOUR_USERNAME');"

# If empty, manually create (or register new user)
```

### "Category not found" Error

Categories weren't seeded. Fix:

```bash
# Restart backend to trigger seeding
docker-compose -f docker-compose.dev.yml restart backend

# Check logs
docker-compose -f docker-compose.dev.yml logs backend | tail -20
```

### Frontend doesn't show categories/members

1. Check browser console for errors
2. Verify API is accessible: http://localhost:8001/docs
3. Check if you're logged in (access_token in localStorage)
4. Verify backend is running: `docker-compose -f docker-compose.dev.yml ps`

### Database connection errors

```bash
# Check if database is running
docker-compose -f docker-compose.dev.yml ps db

# Check database logs
docker-compose -f docker-compose.dev.yml logs db

# Restart database
docker-compose -f docker-compose.dev.yml restart db
```

## Success Criteria

You've successfully tested the expense tracking when you can:

1. ✅ Register a new user and see family auto-created
2. ✅ View 26 default expense categories
3. ✅ Add an expense through the UI
4. ✅ See the expense appear in the list
5. ✅ See correct totals calculated
6. ✅ Delete an expense
7. ✅ See status colors correctly displayed
8. ✅ Add multiple expenses and see them all listed

## Next Steps

After successful testing, the recommended next features to build are:

1. **Edit Transaction Modal** - Allow users to edit existing expenses
2. **Receipt Upload UI** - Drag-and-drop receipt upload interface
3. **Receipt Preview** - View uploaded receipts in modal
4. **Filtering & Search** - Filter by date range, category, member
5. **Dashboard** - Analytics and spending summaries
6. **HSA Account Management** - Track HSA balances and contributions

Would you like me to implement any of these next?
