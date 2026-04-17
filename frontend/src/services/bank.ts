import api from './api'

export interface BankStatus {
  teller_configured: boolean
  active_connections: number
}

export interface BankAccount {
  id: string
  provider: string
  provider_account_id: string
  account_name: string
  account_type: string | null
  account_subtype: string | null
  institution_name: string | null
  last_four: string | null
  currency: string
  is_active: boolean
  last_synced_at: string | null
  created_at: string
  balance_ledger?: string | null
  balance_available?: string | null
  owner_display_name?: string | null
}

export interface MerchantSummary {
  normalized_name: string
  transaction_count: number
  total_amount: string
  first_seen: string
  last_seen: string
  has_hsa: boolean
  hsa_likelihood: 'likely' | 'unlikely' | 'unknown'
}

export interface ManualTransactionCreate {
  transaction_date: string
  amount: string
  merchant_name: string
  description?: string
}

export interface MatchCandidate {
  id: string
  transaction_date: string
  amount: string
  merchant_name: string | null
  description: string | null
  teller_category: string | null
}

export interface BankTransaction {
  id: string
  connection_id: string | null
  source: string
  provider: string | null
  provider_transaction_id: string | null
  transaction_date: string
  description: string | null
  amount: string
  transaction_type: string | null
  status: string
  details: Record<string, unknown> | null
  created_at: string
  // HSA annotations
  is_hsa_eligible: boolean | null
  family_member_id: string | null
  hsa_category: string | null
  eligible_amount: string | null
  reimbursement_status: string | null
  reimbursed_at: string | null
  notes: string | null
  // Denormalised for display
  account_name: string | null
  institution_name: string | null
  document_count: number
  owner_display_name?: string | null
  // Rules engine fields
  auto_flag: 'potential_hsa' | 'hidden' | null
  rule_id: string | null
  // Coverage window
  eligibility_warning: boolean
  // Teller-provided category
  teller_category: string | null
}

export interface BankTransactionAnnotation {
  is_hsa_eligible?: boolean | null
  family_member_id?: string | null
  hsa_category?: string | null
  eligible_amount?: string | null
  reimbursement_status?: string | null
  reimbursed_at?: string | null
  notes?: string | null
  auto_flag?: 'hidden' | null
}

export interface AllTransactionsParams {
  start_date?: string
  end_date?: string
  is_hsa_eligible?: boolean
  include_potential_hsa?: boolean
  family_member_id?: string
  status?: string
  reimbursement_status?: string
  has_documents?: boolean
  search?: string
  show_hidden?: boolean
  auto_flag?: string
  teller_category?: string
  limit?: number
  offset?: number
}

export interface SyncResult {
  added: number
  skipped: number
  account_id: string
}

export const HSA_CATEGORIES = [
  { value: 'medical', label: 'Medical Care' },
  { value: 'dental', label: 'Dental Care' },
  { value: 'vision', label: 'Vision Care' },
  { value: 'prescription', label: 'Prescription' },
  { value: 'otc', label: 'Over-the-Counter' },
  { value: 'mental_health', label: 'Mental Health' },
  { value: 'medical_equipment', label: 'Medical Equipment' },
  { value: 'preventive', label: 'Preventive Care' },
  { value: 'other', label: 'Other HSA' },
]

export interface DashboardSummary {
  hsa_spending: number
  pending_reimbursement: number
  hsa_transaction_count: number
  undocumented_hsa_count: number
  has_family_members: boolean
  has_bank_connections: boolean
  has_synced_transactions: boolean
  has_hsa_transactions: boolean
}

export const bankService = {
  getStatus: () =>
    api.get<BankStatus>('/bank/status').then(r => r.data),

  getDashboardSummary: (params?: { start_date?: string; end_date?: string }) =>
    api.get<DashboardSummary>('/bank/summary', { params }).then(r => r.data),

  connect: (accessToken: string) =>
    api.post<BankAccount[]>('/bank/connect', { access_token: accessToken }).then(r => r.data),

  listAllTransactions: (params?: AllTransactionsParams) =>
    api.get<BankTransaction[]>('/bank/transactions', { params }).then(r => r.data),

  listTransactionCategories: () =>
    api.get<string[]>('/bank/transactions/categories').then(r => r.data),

  countTransactions: (params?: Omit<AllTransactionsParams, 'limit' | 'offset'>) =>
    api.get<number>('/bank/transactions/count', { params }).then(r => r.data),

  annotateTransaction: (id: string, annotation: BankTransactionAnnotation) =>
    api.patch<BankTransaction>(`/bank/transactions/${id}`, annotation).then(r => r.data),

  listAccounts: () =>
    api.get<BankAccount[]>('/bank/accounts').then(r => r.data),

  getAccount: (id: string) =>
    api.get<BankAccount>(`/bank/accounts/${id}`).then(r => r.data),

  syncAccount: (id: string) =>
    api.post<SyncResult>(`/bank/accounts/${id}/sync`).then(r => r.data),

  listTransactions: (id: string, params?: { start_date?: string; end_date?: string; status?: string; limit?: number; offset?: number }) =>
    api.get<BankTransaction[]>(`/bank/accounts/${id}/transactions`, { params }).then(r => r.data),

  disconnectAccount: (id: string) =>
    api.delete(`/bank/accounts/${id}`),

  listMerchants: () =>
    api.get<MerchantSummary[]>('/bank/transactions/merchants').then(r => r.data),

  findMatchingTransactions: (params: { amount: string; date: string; merchant?: string }) =>
    api.get<MatchCandidate[]>('/transactions/match', { params }).then(r => r.data),

  createManualTransaction: (payload: ManualTransactionCreate) =>
    api.post<BankTransaction>('/transactions/', payload).then(r => r.data),

  deleteManualTransaction: (id: string) =>
    api.delete(`/transactions/${id}`),
}
