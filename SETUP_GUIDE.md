# HSA Tracker - Complete Setup Guide

This guide will walk you through setting up HSA Tracker from scratch. **No AWS or Terraform experience required!**

## 🎯 Quick Start (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/hsa-tracker.git
cd hsa-tracker

# 2. Run the interactive setup wizard
make setup-wizard
```

**That's it!** The wizard will guide you through everything step-by-step.

---

## 📋 What You'll Need

### Required
- **Docker Desktop** - [Download here](https://www.docker.com/products/docker-desktop)
- **AWS Account** - [Sign up here](https://aws.amazon.com) (free tier available)

### Recommended
- **Doppler Account** - [Sign up here](https://www.doppler.com) (free tier available)
  - Makes secrets management easy and secure
  - Optional - you can use .env files instead

### Optional
- **AWS CLI** - Helpful for managing AWS but not required
- **Terraform** - The wizard will guide you to install this when needed

---

## 🧙 Setup Wizard Walkthrough

When you run `make setup-wizard`, here's what happens:

### Step 1: Prerequisites Check
The wizard checks if you have Docker installed and running. If not, it will guide you to install it.

### Step 2: Choose Secrets Management

You'll be asked:
> "Do you want to use Doppler for secrets management?"

**Choose Doppler if:**
- ✅ You want the most secure option
- ✅ You might work with a team in the future
- ✅ You want secrets synced across machines
- ✅ You don't mind creating a free account

**Choose .env file if:**
- ✅ You want the simplest option
- ✅ You're working solo
- ✅ You don't want external dependencies

### Step 3: AWS Infrastructure Setup

The wizard will:

1. **Explain what S3 is** (cloud storage for your receipts)
2. **Guide you to create an AWS account** (if you don't have one)
3. **Help you get AWS credentials**:
   - Log in to AWS Console
   - Navigate to Security Credentials
   - Create an Access Key
   - Copy the credentials

4. **Configure your S3 bucket**:
   - Choose AWS region (default: us-east-1)
   - Name your bucket (default: hsa-tracker-receipts-XXXX)
   - Set lifecycle policies (auto-archive old receipts)

5. **Run Terraform automatically**:
   - Creates your S3 bucket
   - Sets up access credentials
   - Configures encryption and security
   - Takes about 30-60 seconds

### Step 4: Application Configuration

The wizard will:
- Generate secure random secrets (for passwords, JWT tokens, etc.)
- Store everything in Doppler (or .env file)
- Set up database credentials
- Configure all application settings

### Step 5: Start the Application

The wizard will:
- Start Docker containers (database, backend, frontend)
- Run database migrations
- Verify everything is working

### Done! 🎉

You'll see:
```
🎉 Setup Complete!

Access your application:
  Frontend: http://localhost:3000
  Backend API: http://localhost:8000
  API Docs: http://localhost:8000/docs

Next steps:
  1. Open http://localhost:3000 in your browser
  2. Click 'Create one' to register your first user
  3. Start tracking your HSA expenses!
```

---

## 🔐 Understanding Secrets

### What Secrets Are Stored?

**AWS Credentials (2 types - this is important!):**

1. **Your AWS Account Credentials** (for Terraform):
   - Used ONLY to create the S3 bucket
   - Never stored in the app
   - You enter these during setup

2. **S3 Access Credentials** (for the app):
   - Created BY Terraform
   - Used BY the app to upload/download receipts
   - Automatically stored in Doppler or .env

**Application Secrets:**
- `SECRET_KEY` - For general encryption
- `JWT_SECRET_KEY` - For user sessions
- `DATABASE_PASSWORD` - For database access

**All secrets are automatically generated** - you don't need to create them!

### Doppler vs .env File

**With Doppler:**
```bash
# View secrets
doppler secrets

# Edit a secret
doppler secrets set SECRET_KEY=new-value

# Run commands with secrets
doppler run -- docker-compose up
```

**With .env file:**
```bash
# View secrets
cat .env

# Edit secrets
nano .env

# Run commands (secrets loaded automatically)
docker-compose up
```

**The Makefile automatically detects** which method you're using and handles it for you!

---

## 🚀 Using the Application

### First Time Setup

1. **Open the app**: http://localhost:3000
2. **Click "Create one"** to register
3. **Fill in**:
   - Full Name
   - Email (used as username only, no emails sent!)
   - Password (8+ characters)
4. **Click "Create Account"**
5. **You're in!** Start tracking expenses

### Daily Use

```bash
# Start the app
make dev-up

# View logs (if something's wrong)
make dev-logs

# Stop the app
make dev-down
```

### Add an Expense

1. Go to **Transactions** page
2. Click **Add Transaction**
3. Fill in:
   - Family member
   - Date
   - Amount
   - Category (Medical, Dental, etc.)
   - Merchant
4. **Upload receipt** (optional but recommended)
5. **Save**

### Set Up 2FA (Optional)

1. In the app, go to **Settings** (when implemented)
2. Click **Set up 2FA**
3. **Scan QR code** with your authenticator app (Google Authenticator, Authy, etc.)
4. **Enter the 6-digit code** to verify
5. **Save backup codes** somewhere safe!

---

## 🛠️ Common Tasks

### View All Available Commands
```bash
make help
```

### Check Secrets
```bash
# If using Doppler
doppler secrets

# If using .env
cat .env
```

### Update a Secret
```bash
# If using Doppler
doppler secrets set SECRET_KEY=new-value

# If using .env
nano .env  # Edit the file
```

### Reset Everything (Start Fresh)
```bash
make clean
make setup-wizard
```

### Update AWS Infrastructure
```bash
cd terraform
nano terraform.tfvars  # Edit settings
terraform apply
```

---

## 🆘 Troubleshooting

### "Docker is not running"
**Solution:** Start Docker Desktop and try again

### "Doppler CLI not found"
**Solution:**
```bash
# macOS
brew install dopplerhq/cli/doppler

# Linux
curl -sLf https://cli.doppler.com/install.sh | sh

# Windows
scoop install doppler
```

### "AWS credentials are invalid"
**Solution:**
1. Go to AWS Console → Security Credentials
2. Create a new access key
3. Run `make setup-wizard` again with new credentials

### "Terraform not found"
**Solution:**
```bash
# macOS
brew install terraform

# Linux/Windows
# Download from: https://www.terraform.io/downloads
```

### "Port already in use"
**Solution:**
```bash
# Find what's using the port
lsof -i :3000  # Frontend
lsof -i :8000  # Backend
lsof -i :5432  # Database

# Kill the process or change ports in docker-compose.dev.yml
```

### "Database migration failed"
**Solution:**
```bash
# Reset and try again
make db-reset
make db-upgrade
```

### "Can't login after registration"
**Solution:**
```bash
# Check backend logs
make dev-logs

# Verify database is running
docker ps

# Try restarting
make dev-down
make dev-up
```

---

## 🔧 Advanced Configuration

### Change Database from PostgreSQL to SQLite

In Doppler or .env:
```bash
DATABASE_TYPE=sqlite
DATABASE_URL=sqlite:///./data/hsatracker.db
```

### Use External PostgreSQL Database

In Doppler or .env:
```bash
DATABASE_URL=postgresql://user:pass@your-server:5432/dbname
```

### Change JWT Token Expiration

In Doppler or .env:
```bash
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60  # 1 hour
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30    # 30 days
```

### Add More CORS Origins (for production)

In Doppler or .env:
```bash
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

---

## 📊 Cost Breakdown

### AWS S3 Costs

**Typical usage (individual/family):**
- Storage: ~$0.50-2/month (depending on receipt volume)
- Requests: ~$0.10-0.50/month (uploads/downloads)
- **Total: $1-5/month**

**AWS Free Tier:**
- 5 GB storage (first 12 months)
- 20,000 GET requests/month
- 2,000 PUT requests/month

### Doppler Costs

- **Free tier:** 5 users, unlimited secrets, unlimited projects
- **Most users need:** Free tier is sufficient

### Total Monthly Cost

**Year 1 (with free tier):** ~$0-2/month
**After year 1:** ~$1-5/month

---

## 🎓 Next Steps

After setup, check out:

- **[FEATURES.md](./FEATURES.md)** - See what features are available
- **[AUTH_COMPLETE_SUMMARY.md](./AUTH_COMPLETE_SUMMARY.md)** - Learn about authentication
- **[CONTRIBUTING.md](./CONTRIBUTING.md)** - Want to contribute?

---

## ❓ FAQ

### Do I need to know AWS?
**No!** The wizard handles everything. You just need to:
1. Create an AWS account
2. Get an access key (wizard shows you how)
3. That's it!

### Do I need to know Terraform?
**No!** The wizard runs Terraform for you automatically.

### Do I need to know Docker?
**No!** Just install Docker Desktop and the wizard does the rest.

### Will you send emails with my receipts?
**No!** All data stays on your computer and in YOUR AWS account.

### Can I use this without internet?
**Mostly yes:**
- The app runs locally
- TOTP 2FA works offline
- You need internet only to upload/download receipts from S3

### Can I backup my data?
**Yes!**
```bash
# Backup database
docker-compose -f docker-compose.dev.yml exec db pg_dump -U hsatracker hsatracker > backup.sql

# Restore database
docker-compose -f docker-compose.dev.yml exec -T db psql -U hsatracker hsatracker < backup.sql
```

Receipts are automatically backed up in S3 with versioning enabled!

### How do I uninstall?
```bash
# Stop containers
make dev-down

# Delete AWS infrastructure (S3 bucket and receipts!)
cd terraform
terraform destroy

# Delete code
cd ..
rm -rf hsa-tracker/
```

---

**Need more help?** Open an issue on GitHub or check the other documentation files!
