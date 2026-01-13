/**
 * TypeScript types for transactions, receipts, and categories
 */

export enum PaymentMethod {
  HSA_CARD = 'hsa_card',
  PERSONAL = 'personal',
  OTHER = 'other',
}

export enum ReimbursementStatus {
  NOT_NEEDED = 'not_needed',
  PENDING = 'pending',
  REIMBURSED = 'reimbursed',
  NOT_SEEKING = 'not_seeking',
}

export interface Transaction {
  id: string
  family_id: string
  family_member_id: string
  category_id: string
  hsa_account_id?: string
  transaction_date: string // ISO date string
  amount: number
  merchant_name?: string
  description?: string
  payment_method: PaymentMethod
  reimbursement_status: ReimbursementStatus
  reimbursed_date?: string // ISO date string
  tax_year: number
  created_by_user_id?: string
  created_at: string
  updated_at: string
}

export interface TransactionCreate {
  family_member_id: string
  category_id: string
  transaction_date: string // ISO date string
  amount: number
  merchant_name?: string
  description?: string
  payment_method: PaymentMethod
  reimbursement_status: ReimbursementStatus
  reimbursed_date?: string // ISO date string
  tax_year?: number
  hsa_account_id?: string
}

export interface TransactionUpdate {
  family_member_id?: string
  category_id?: string
  transaction_date?: string
  amount?: number
  merchant_name?: string
  description?: string
  payment_method?: PaymentMethod
  reimbursement_status?: ReimbursementStatus
  reimbursed_date?: string
  tax_year?: number
  hsa_account_id?: string
}

export interface TransactionListResponse {
  transactions: Transaction[]
  total: number
  skip: number
  limit: number
}

export interface TransactionFilters {
  family_member_id?: string
  category_id?: string
  start_date?: string
  end_date?: string
  min_amount?: number
  max_amount?: number
  payment_method?: PaymentMethod
  reimbursement_status?: ReimbursementStatus
  tax_year?: number
  search?: string
  skip?: number
  limit?: number
}

export interface Category {
  id: string
  family_id?: string
  name: string
  description?: string
  is_hsa_eligible: boolean
  parent_category_id?: string
  is_system_category: boolean
  created_at: string
}

export interface CategoryCreate {
  name: string
  description?: string
  is_hsa_eligible: boolean
  parent_category_id?: string
}

export interface Receipt {
  id: string
  transaction_id: string
  file_name: string
  file_size: number
  mime_type: string
  s3_key: string
  s3_bucket: string
  thumbnail_s3_key?: string
  upload_date: string
  uploaded_by_user_id?: string
  created_at: string
}

export interface ReceiptUploadUrl {
  upload_url: string
  s3_key: string
  fields: Record<string, string>
  transaction_id: string
}

export interface ReceiptCreate {
  file_name: string
  file_size: number
  mime_type: string
  s3_key: string
  s3_bucket: string
  thumbnail_s3_key?: string
}

export interface FamilyMember {
  id: string
  family_id: string
  user_id?: string
  name: string
  relationship: 'self' | 'spouse' | 'child' | 'other'
  date_of_birth?: string
  is_tax_dependent: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

// Helper functions for display
export const getPaymentMethodLabel = (method: PaymentMethod): string => {
  switch (method) {
    case PaymentMethod.HSA_CARD:
      return 'HSA Card'
    case PaymentMethod.PERSONAL:
      return 'Personal Card/Cash'
    case PaymentMethod.OTHER:
      return 'Other'
    default:
      return method
  }
}

export const getReimbursementStatusLabel = (status: ReimbursementStatus): string => {
  switch (status) {
    case ReimbursementStatus.NOT_NEEDED:
      return 'Not Needed'
    case ReimbursementStatus.PENDING:
      return 'Pending Reimbursement'
    case ReimbursementStatus.REIMBURSED:
      return 'Reimbursed'
    case ReimbursementStatus.NOT_SEEKING:
      return 'Not Seeking Reimbursement'
    default:
      return status
  }
}

export const getReimbursementStatusColor = (status: ReimbursementStatus): string => {
  switch (status) {
    case ReimbursementStatus.NOT_NEEDED:
      return 'text-gray-600 bg-gray-100'
    case ReimbursementStatus.PENDING:
      return 'text-yellow-700 bg-yellow-100'
    case ReimbursementStatus.REIMBURSED:
      return 'text-green-700 bg-green-100'
    case ReimbursementStatus.NOT_SEEKING:
      return 'text-blue-700 bg-blue-100'
    default:
      return 'text-gray-600 bg-gray-100'
  }
}
