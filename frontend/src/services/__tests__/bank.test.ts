import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}))

import api from '../api'
import { bankService } from '../bank'

const mockAccount = {
  id: 'acct-uuid-1',
  provider: 'teller',
  provider_account_id: 'acct_001',
  account_name: 'HSA Checking',
  account_type: 'depository',
  account_subtype: 'hsa',
  institution_name: 'First National Bank',
  last_four: '1234',
  currency: 'USD',
  is_active: true,
  last_synced_at: null,
  created_at: '2026-03-22T00:00:00',
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('bankService.getStatus', () => {
  it('calls GET /bank/status and returns data', async () => {
    const mockStatus = { provider_configured: true, active_connections: 2 }
    ;(api.get as any).mockResolvedValue({ data: mockStatus })

    const result = await bankService.getStatus()

    expect(api.get).toHaveBeenCalledWith('/bank/status')
    expect(result).toEqual(mockStatus)
  })
})

describe('bankService.connect', () => {
  it('POSTs setup_token and returns created accounts', async () => {
    ;(api.post as any).mockResolvedValue({ data: [mockAccount] })

    const result = await bankService.connect('aHR0cHM6Ly9leGFtcGxlLmNvbQ==')

    expect(api.post).toHaveBeenCalledWith('/bank/connect', { setup_token: 'aHR0cHM6Ly9leGFtcGxlLmNvbQ==' })
    expect(result).toHaveLength(1)
    expect(result[0].provider_account_id).toBe('acct_001')
  })
})

describe('bankService.listAccounts', () => {
  it('calls GET /bank/accounts', async () => {
    ;(api.get as any).mockResolvedValue({ data: [mockAccount] })

    const result = await bankService.listAccounts()

    expect(api.get).toHaveBeenCalledWith('/bank/accounts')
    expect(result).toHaveLength(1)
  })

  it('returns empty array when no accounts', async () => {
    ;(api.get as any).mockResolvedValue({ data: [] })
    const result = await bankService.listAccounts()
    expect(result).toEqual([])
  })
})

describe('bankService.getAccount', () => {
  it('calls GET /bank/accounts/:id', async () => {
    const withBalance = { ...mockAccount, balance_ledger: '4250.00', balance_available: '4250.00' }
    ;(api.get as any).mockResolvedValue({ data: withBalance })

    const result = await bankService.getAccount('acct-uuid-1')

    expect(api.get).toHaveBeenCalledWith('/bank/accounts/acct-uuid-1')
    expect(result.balance_ledger).toBe('4250.00')
  })
})

describe('bankService.syncAccount', () => {
  it('POSTs to sync endpoint and returns result', async () => {
    const syncResult = { added: 5, skipped: 2, account_id: 'acct-uuid-1' }
    ;(api.post as any).mockResolvedValue({ data: syncResult })

    const result = await bankService.syncAccount('acct-uuid-1')

    expect(api.post).toHaveBeenCalledWith('/bank/accounts/acct-uuid-1/sync')
    expect(result.added).toBe(5)
    expect(result.skipped).toBe(2)
  })
})

describe('bankService.listTransactions', () => {
  it('calls GET /bank/accounts/:id/transactions without params', async () => {
    ;(api.get as any).mockResolvedValue({ data: [] })

    await bankService.listTransactions('acct-uuid-1')

    expect(api.get).toHaveBeenCalledWith('/bank/accounts/acct-uuid-1/transactions', { params: undefined })
  })

  it('forwards filter params', async () => {
    ;(api.get as any).mockResolvedValue({ data: [] })

    await bankService.listTransactions('acct-uuid-1', {
      start_date: '2026-01-01',
      end_date: '2026-03-31',
      status: 'posted',
      limit: 50,
    })

    expect(api.get).toHaveBeenCalledWith('/bank/accounts/acct-uuid-1/transactions', {
      params: { start_date: '2026-01-01', end_date: '2026-03-31', status: 'posted', limit: 50 },
    })
  })
})

describe('bankService.disconnectAccount', () => {
  it('calls DELETE /bank/accounts/:id', async () => {
    ;(api.delete as any).mockResolvedValue({ data: null })

    await bankService.disconnectAccount('acct-uuid-1')

    expect(api.delete).toHaveBeenCalledWith('/bank/accounts/acct-uuid-1')
  })
})
