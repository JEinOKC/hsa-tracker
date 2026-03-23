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
}

export interface BankTransaction {
  id: string
  connection_id: string
  provider: string
  provider_transaction_id: string
  transaction_date: string
  description: string | null
  amount: string
  transaction_type: string | null
  status: string
  details: Record<string, unknown> | null
  created_at: string
}

export interface SyncResult {
  added: number
  skipped: number
  account_id: string
}

export const bankService = {
  getStatus: () =>
    api.get<BankStatus>('/bank/status').then(r => r.data),

  connect: (accessToken: string) =>
    api.post<BankAccount[]>('/bank/connect', { access_token: accessToken }).then(r => r.data),

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
}
