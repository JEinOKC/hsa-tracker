import api from './api'

// ─── Types ────────────────────────────────────────────────────────────────────

export type AccountType = 'contribution' | 'investment' | 'both'

export interface HsaHolding {
  id: string
  account_id: string
  ticker: string
  shares: string
  last_known_price: string | null
  last_price_fetched_at: string | null
  created_at: string
  updated_at: string
}

export interface HsaAccount {
  id: string
  user_id: string
  institution_name: string
  nickname: string | null
  account_type: AccountType
  is_active: boolean
  cash_balance: string | null
  cash_balance_updated_at: string | null
  last_checkin_at: string | null
  holdings: HsaHolding[]
  created_at: string
  updated_at: string
}

export interface AccountSummary {
  account_id: string
  institution_name: string
  nickname: string | null
  cash_balance: string | null
  invested_value: string | null
  total_value: string | null
  holdings_count: number
  last_checkin_at: string | null
}

export interface PortfolioSummary {
  accounts: AccountSummary[]
  total_value: string | null
}

export interface ProjectionPoint {
  year: number
  value: string
}

export interface ProjectionResult {
  starting_value: string
  annual_return: number
  points: ProjectionPoint[]
}

export interface PortfolioHistoryPoint {
  date: string
  total_value: string
}

export interface PortfolioHistoryOut {
  points: PortfolioHistoryPoint[]
}

// ─── Service ──────────────────────────────────────────────────────────────────

export const portfolioService = {
  // Accounts
  listAccounts(): Promise<HsaAccount[]> {
    return api.get('/portfolio/accounts').then(r => r.data)
  },

  createAccount(data: {
    institution_name: string
    nickname?: string
    account_type?: AccountType
    cash_balance?: string | null
  }): Promise<HsaAccount> {
    return api.post('/portfolio/accounts', data).then(r => r.data)
  },

  updateAccount(id: string, data: Partial<{
    institution_name: string
    nickname: string | null
    account_type: AccountType
    is_active: boolean
    cash_balance: string | null
  }>): Promise<HsaAccount> {
    return api.patch(`/portfolio/accounts/${id}`, data).then(r => r.data)
  },

  deleteAccount(id: string): Promise<void> {
    return api.delete(`/portfolio/accounts/${id}`)
  },

  // Holdings
  listHoldings(accountId: string): Promise<HsaHolding[]> {
    return api.get(`/portfolio/accounts/${accountId}/holdings`).then(r => r.data)
  },

  addHolding(accountId: string, data: { ticker: string; shares: string }): Promise<HsaHolding> {
    return api.post(`/portfolio/accounts/${accountId}/holdings`, data).then(r => r.data)
  },

  updateHolding(accountId: string, holdingId: string, data: Partial<{
    ticker: string
    shares: string
    last_known_price: string | null
  }>): Promise<HsaHolding> {
    return api.patch(`/portfolio/accounts/${accountId}/holdings/${holdingId}`, data).then(r => r.data)
  },

  deleteHolding(accountId: string, holdingId: string): Promise<void> {
    return api.delete(`/portfolio/accounts/${accountId}/holdings/${holdingId}`)
  },

  // Prices
  refreshPrices(): Promise<{ updated: number; tickers_fetched: number; not_found: string[] }> {
    return api.post('/portfolio/prices/refresh').then(r => r.data)
  },

  // Summary
  getSummary(): Promise<PortfolioSummary> {
    return api.get('/portfolio/summary').then(r => r.data)
  },

  // Projection
  getProjection(params: {
    years?: number
    annual_return?: number
  }): Promise<ProjectionResult> {
    return api.get('/portfolio/projection', { params }).then(r => r.data)
  },

  // History
  getHistory(days: number): Promise<PortfolioHistoryOut> {
    return api.get('/portfolio/history', { params: { days } }).then(r => r.data)
  },
}
