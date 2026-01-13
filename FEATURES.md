# HSA Tracker - Feature Requirements Research

## Executive Summary

This document outlines the research findings and feature requirements for building a self-hosted HSA (Health Savings Account) expense tracking application designed for families. The application will help families track HSA-eligible expenses, manage receipts, ensure compliance with IRS regulations, and simplify tax reporting.

---

## 1. HSA Background & Regulatory Requirements

### 2026 Contribution Limits
- **Self-only HDHP coverage**: $4,400 (up from $4,300 in 2025)
- **Family HDHP coverage**: $8,750 (up from $8,550 in 2025)
- **Age 55+ catch-up contribution**: $1,000 (unchanged)

### Key 2026 Changes
- Bronze and catastrophic plans available through an Exchange are now HSA-compatible (effective Jan 1, 2026)
- Telehealth and remote care services can be received before meeting HDHP deductible while maintaining HSA eligibility (permanent as of Jan 1, 2025)
- Direct Primary Care (DPC) membership fees are now classified as qualified medical expenses

### Qualified Medical Expenses
HSA funds can be used for qualified medical expenses for:
- The account beneficiary
- The beneficiary's spouse
- Tax dependents claimed on the beneficiary's tax return

**Important**: Expenses incurred before establishing the HSA are NOT qualified medical expenses.

### Tax Reporting Requirements
- Must file Form 8889 with tax return if HSA distributions were received
- Non-qualified distributions are includible in gross income and subject to 20% additional tax (with limited exceptions)
- Critical: HSA funds can only be used for dependents who are tax dependents, not just those covered under health insurance

---

## 2. Core Features Required

### 2.1 Expense Tracking & Management

#### Transaction Entry
- **Quick transaction entry**: Simple form to log expenses quickly
- **Multiple entry methods**:
  - Manual entry
  - Receipt scanning with OCR (Optical Character Recognition)
  - Bulk import from CSV/bank statements
- **Transaction details**:
  - Date of expense
  - Merchant/provider name
  - Amount
  - Expense category (medical, dental, vision, prescription, etc.)
  - Description/notes
  - Payment method (HSA debit card, personal payment for reimbursement, etc.)
  - Reimbursement status

#### Categorization
- **Pre-defined HSA-eligible categories**:
  - Medical care and services
  - Dental care
  - Vision care
  - Prescription medications
  - Over-the-counter medications
  - Medical equipment and supplies
  - Mental health services
  - Preventive care
  - COVID-19 testing and PPE
  - Menstrual care products
  - Direct Primary Care (DPC) fees
- **Custom categories**: Allow users to create additional subcategories
- **Category validation**: Flag potentially non-eligible expenses for user review
- **Bulk categorization**: Apply categories to multiple transactions at once

### 2.2 Receipt Management

#### Receipt Storage
- **Multiple receipts per transaction**: Allow uploading multiple receipt images/PDFs for a single expense
- **Supported formats**: Images (JPG, PNG, HEIC), PDFs, scanned documents
- **Receipt scanning**:
  - Snap photos directly from mobile device
  - Upload from computer
  - OCR to extract key information (date, amount, merchant)
- **Cloud backup**: Secure, encrypted storage of receipts
- **Receipt organization**: Search and filter receipts by date, amount, category, or family member

#### Receipt Validation
- **Required receipts**: Flag transactions that need receipt documentation
- **Receipt matching**: Link receipts to corresponding transactions
- **Missing receipt alerts**: Notify users of expenses without supporting documentation

### 2.3 Family Member Management

#### Multi-User Support
- **Family member profiles**:
  - Name
  - Relationship to account holder
  - Tax dependent status (critical for compliance)
  - Date of birth
  - Active/inactive status
- **Expense attribution**: Tag each expense to a specific family member
- **Dependent tracking**: Track which family members qualify as tax dependents
- **Aging dependents alert**: Notify when dependents approach age where they may no longer qualify

#### Permissions & Access
- **Account holder**: Full access to all features
- **Secondary users**: Optionally allow spouse or other family members to:
  - Add expenses
  - Upload receipts
  - View reports (with configurable permissions)
- **Individual vs. family view**: Toggle between seeing all family expenses or individual member expenses

### 2.4 Reimbursement Tracking

#### Reimbursement Management
- **Reimbursement status**:
  - Paid with HSA funds (no reimbursement needed)
  - Pending reimbursement
  - Reimbursed
  - Not seeking reimbursement
- **Reimbursement batches**: Group expenses for batch reimbursement requests
- **Historical reimbursement**: Track when expenses were reimbursed
- **Out-of-pocket tracking**: Calculate total unreimbursed eligible expenses

#### Strategic Reimbursement
- **Deferred reimbursement tracking**: Support strategy of paying out-of-pocket and tracking for future reimbursement
- **Age tracking**: Show how long expenses have been unreimbursed
- **Reimbursement calculator**: Calculate total available for reimbursement from past expenses

### 2.5 Account Balance & Contribution Tracking

#### HSA Account Management
- **Current balance tracking**: Monitor HSA account balance
- **Multiple HSA accounts**: Support tracking multiple HSA accounts (e.g., spousal HSAs)
- **Contribution tracking**:
  - Annual contribution limits (self-only vs. family)
  - Contributions made to date
  - Remaining contribution room
  - Catch-up contribution eligibility (age 55+)
- **Contribution source tracking**: Distinguish between employee, employer, and other contributions

#### Balance Projections
- **Year-end projections**: Estimate end-of-year balance based on contribution plans and spending patterns
- **Contribution recommendations**: Suggest optimal contribution amounts based on expected expenses

### 2.6 Reporting & Analytics

#### Financial Reports
- **Spending by category**: Breakdown of expenses by category (medical, dental, vision, etc.)
- **Spending by family member**: See which family members incur most expenses
- **Monthly/yearly spending trends**: Visualize spending patterns over time
- **Comparison reports**: Compare spending across years
- **Reimbursement summary**: Total pending, completed, and available reimbursements

#### Tax Reports
- **Annual tax summary**: Prepare data for Form 8889
- **Total distributions**: Sum of all HSA withdrawals/payments
- **Total qualified expenses**: Sum of all eligible medical expenses
- **Non-qualified distributions**: Flag any potentially non-qualified expenses
- **Export for tax preparation**: CSV/PDF export formatted for tax software

#### Visual Analytics
- **Dashboard**: At-a-glance overview of:
  - Current HSA balance
  - YTD spending
  - Contribution status
  - Pending reimbursements
  - Upcoming contribution deadlines
- **Charts and graphs**:
  - Spending trends over time
  - Category breakdown (pie/bar charts)
  - Balance vs. spending over time
  - Family member expense comparison

### 2.7 Compliance & Validation

#### IRS Compliance Features
- **Eligibility checker**: Help users determine if expenses are HSA-eligible
- **Built-in expense database**: Comprehensive list of qualified medical expenses per IRS Publication 502
- **Dependent qualification checking**: Verify dependents meet IRS requirements
- **Contribution limit enforcement**: Warn users approaching or exceeding contribution limits
- **Tax year management**: Properly attribute expenses to correct tax years

#### Audit Preparation
- **Complete expense documentation**: All expenses with receipts and details
- **Audit trail**: Track when expenses were entered, modified, or categorized
- **Export functionality**: Generate audit-ready reports with all supporting documentation
- **Receipt package export**: Bundle all receipts for a given period

### 2.8 Data Management & Security

#### Data Import/Export
- **Bank/HSA provider integration**: Import transactions from HSA provider (CSV, OFX, QFX)
- **Manual import**: CSV upload for bulk transaction entry
- **Export options**: CSV, JSON, PDF exports for backup or migration
- **Backup and restore**: Regular automated backups with restore functionality

#### Security & Privacy
- **Self-hosted deployment**: Full control over data location
- **Encrypted storage**: Encrypt sensitive data at rest
- **Secure access**: Authentication and authorization
- **HTTPS/TLS**: Encrypted data transmission
- **Access logs**: Track who accessed what data and when
- **Data retention policies**: Configurable retention (IRS recommends keeping records for 3+ years)

---

## 3. Technical Architecture Considerations

### 3.1 Deployment Options
- **Docker containerization**: Easy deployment with Docker Compose
- **Database options**: Support for PostgreSQL, MySQL, or SQLite
- **Web-based interface**: Responsive design for desktop and mobile browsers
- **Mobile app considerations**: Progressive Web App (PWA) for mobile access

### 3.2 Technology Stack Suggestions
- **Backend**:
  - Node.js + Express, or
  - Python + FastAPI/Django, or
  - Go for performance
- **Frontend**:
  - React, Vue, or Svelte for modern UI
  - TailwindCSS or Material-UI for styling
  - Chart.js or Recharts for visualizations
- **Database**:
  - PostgreSQL (recommended for production)
  - SQLite (for simple deployments)
- **Storage**:
  - Local filesystem storage for receipts
  - Optional S3-compatible storage (MinIO, etc.)
- **OCR**:
  - Tesseract.js for client-side OCR
  - Cloud OCR services (Google Cloud Vision, Azure) as optional enhancement

### 3.3 Data Model (Key Entities)
```
- Users (account holders, family members)
- HSA Accounts (one or more per family)
- Transactions (expenses)
- Receipts (linked to transactions)
- Categories (HSA-eligible expense types)
- Reimbursements (tracking reimbursement requests)
- Contributions (tracking HSA contributions)
- Tax Years (for reporting and compliance)
```

---

## 4. Family-Specific Requirements

### 4.1 Multi-Member Coordination
- **Shared expense pool**: Multiple family members can add expenses to same HSA account
- **Duplicate detection**: Alert if similar expenses are entered by multiple users
- **Activity feed**: See recent activity by all family members
- **Notifications**: Alert family members of important events (contribution limits, missing receipts, etc.)

### 4.2 Dependent Management
- **Tax dependent tracking**: Critical distinction between health insurance dependents and tax dependents
- **Dependent aging**: Track when dependents turn 26 or otherwise lose dependent status
- **Dependent qualification rules**: Educational content about IRS dependent requirements
- **Split families**: Handle scenarios with divorced parents, shared custody, etc.

### 4.3 Spousal Coordination
- **Dual HSA support**: Both spouses may have separate HSAs
- **Contribution allocation**: Track how family contribution limit is split between spouse HSAs
- **Shared expenses**: Track which HSA paid for which expenses
- **Joint reporting**: Combined tax reporting view

---

## 5. User Experience Considerations

### 5.1 Ease of Use
- **Minimal data entry**: OCR and smart defaults to reduce typing
- **Mobile-first**: Most expenses captured on-the-go
- **Quick capture**: Snap receipt → auto-categorize → done
- **Intuitive navigation**: Clear menu structure and workflows

### 5.2 Educational Content
- **In-app help**: Tooltips and explanations for HSA concepts
- **Eligibility guide**: Searchable database of qualified expenses
- **FAQ section**: Common questions about HSA usage
- **Links to IRS resources**: Direct links to Publications 502, 969, and Form 8889

### 5.3 Notifications & Reminders
- **Contribution deadline reminders**: Alert before tax day for prior year contributions
- **Missing receipts**: Periodic reminders for expenses without receipts
- **Unusual expenses**: Flag transactions that might not be qualified
- **Year-end summary**: Annual recap of HSA activity

---

## 6. Competitive Analysis

### 6.1 Existing Solutions
- **TrackHSA**: Cloud-based receipt tracking with multiple receipt uploads per expense
- **HSA Store ExpenseTracker**: Free app with receipt scanning and purchase tracking
- **HSA Central**: Receipt organizer with photo upload and descriptive labels
- **Prosaver**: AI-powered receipt extraction and transaction creation
- **General finance apps**: Mint, YNAB, Personal Capital (lack HSA-specific features)

### 6.2 Self-Hosted Finance Apps
- **Firefly III**: Full-featured double-entry accounting, budgets, multi-currency
- **Actual Budget**: Envelope budgeting with self-hosted sync
- **ExpenseOwl**: Simple expense tracking with visualizations
- **GnuCash**: Comprehensive accounting system

### 6.3 Gaps in Existing Solutions
- **No self-hosted HSA-specific tracker**: All HSA-specific apps are cloud-based SaaS
- **Limited family features**: Most apps don't handle multi-member families well
- **Missing tax compliance**: Few apps prepare data specifically for Form 8889
- **Reimbursement tracking**: Most apps don't support deferred reimbursement strategy
- **Dependent qualification**: No apps validate tax dependent requirements

---

## 7. Recommended MVP Features (Phase 1)

To build a minimum viable product, prioritize these features:

1. **Basic transaction management**:
   - Manual transaction entry
   - Basic categorization (pre-defined categories)
   - Transaction listing and search

2. **Receipt management**:
   - Upload receipt images
   - Link receipts to transactions
   - View/download receipts

3. **Family member tracking**:
   - Create family member profiles
   - Tag transactions to family members
   - Mark tax dependent status

4. **Account balance tracking**:
   - Track current HSA balance
   - Log contributions
   - Display contribution limits and progress

5. **Basic reporting**:
   - Simple dashboard with key metrics
   - Annual spending summary
   - Spending by category and family member

6. **Security basics**:
   - User authentication
   - Encrypted data storage
   - Self-hosted deployment with Docker

7. **Export functionality**:
   - CSV export of transactions
   - Basic tax year summary report

---

## 8. Future Enhancements (Phase 2+)

After MVP, consider these enhancements:

1. **OCR and AI**:
   - Automatic receipt data extraction
   - Smart expense categorization
   - Duplicate detection

2. **Advanced analytics**:
   - Spending trends and predictions
   - Budget planning and tracking
   - Multi-year comparisons

3. **Bank integration**:
   - Direct import from HSA providers
   - Automatic transaction creation
   - Balance syncing

4. **Mobile app**:
   - Native iOS/Android apps
   - Camera integration for receipts
   - Push notifications

5. **Reimbursement features**:
   - Reimbursement request generation
   - Batch reimbursement processing
   - Reimbursement history tracking

6. **Multi-HSA support**:
   - Track multiple HSA accounts
   - Spousal HSA coordination
   - Transfer tracking between accounts

7. **Compliance automation**:
   - Automatic Form 8889 data preparation
   - IRS Publication 502 integration
   - Expense eligibility validation

---

## 9. Resources & References

### IRS Documentation
- [Publication 969 (2024) - Health Savings Accounts](https://www.irs.gov/publications/p969)
- [Publication 502 - Medical and Dental Expenses](https://www.irs.gov/publications/p502)
- [Instructions for Form 8889](https://www.irs.gov/instructions/i8889)
- [IRS Qualified Medical Expenses - HSA Bank](https://www.hsabank.com/HSABank/Learning-Center/IRS-qualified-medical-expenses)

### HSA Information & Limits
- [GoodRx - 92 HSA-Eligible Expenses for 2026](https://www.goodrx.com/insurance/fsa-hsa/hsa-eligible-expenses)
- [Keenan - IRS Announces 2026 HSA and HDHP Limits](https://www.keenan.com/knowledge-center/news-and-insights/blogs/irs-announces-2026-hsa-and-hdhp-limits/)
- [Fidelity - HSA Contribution Limits and Eligibility Rules](https://www.fidelity.com/learning-center/smart-money/hsa-contribution-limits)
- [HealthCareInsider - HSA Changes 2026](https://healthcareinsider.com/hsa-changes-2026-rules-contribution-limits)

### Family & Dependent Rules
- [Further - How Spouses and Domestic Partners Can Manage HSAs](https://learn.hellofurther.com/Individuals/Life_Changes/How_Spouses_and_Domestic_Partners_can_Manage_an_HSA)
- [Ascensus - How HSA Contributions Can Be Split Between Family Members](https://thelink.ascensus.com/articles/2025/5/12/how-can-hsa-contributions-be-split-between-family-members)
- [American Fidelity - HSA Mistakes to Avoid: Dependent Rules](https://americanfidelity.com/blog/reimburse/hsa-mistakes-to-avoid-dependents)

### Existing HSA Tracking Solutions
- [TrackHSA - Features](https://www.trackhsa.com/features)
- [White Coat Investor - Best Way to Track HSA Receipts](https://www.whitecoatinvestor.com/the-best-way-to-track-your-hsa-receipts/)
- [HSA Store ExpenseTracker](https://hsastore.com/expensetracker-app.html)
- [Silver - Automatically Collect HSA Eligible Expenses](https://www.withsilver.app/)

### Self-Hosted Finance Applications
- [Firefly III - GitHub](https://github.com/firefly-iii/firefly-iii)
- [Firefly III - Official Site](https://firefly-iii.org/)
- [awesome-selfhosted - Money & Budgeting](https://awesome-selfhosted.net/tags/money-budgeting--management.html)
- [ExpenseOwl - GitHub](https://github.com/Tanq16/ExpenseOwl)
- [Actual Budget](https://actualbudget.org/)

---

## 10. Conclusion

Building a self-hosted HSA tracker for families addresses a clear gap in the current market. While several cloud-based HSA expense trackers exist, none offer the privacy, control, and customization of a self-hosted solution. Similarly, while many self-hosted finance apps exist, none are purpose-built for HSA compliance and family tracking.

The key differentiators for this application should be:
1. **HSA-specific compliance**: Built-in understanding of IRS rules and qualified expenses
2. **Family-focused**: Proper handling of multiple family members and tax dependent requirements
3. **Self-hosted**: Complete data ownership and privacy
4. **Tax preparation**: Streamlined data collection and reporting for Form 8889
5. **Receipt management**: Comprehensive receipt storage and organization
6. **Reimbursement tracking**: Support for deferred reimbursement strategies

Starting with a focused MVP and iterating based on user feedback will allow for a lean development approach while ensuring the core value proposition is delivered early.
