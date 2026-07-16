import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '../../test/utils'
import BankAccounts from '../BankAccounts'

vi.mock('../../services/bank', () => ({
  bankService: {
    listAccounts: vi.fn(),
    connect: vi.fn(),
    syncAccount: vi.fn(),
    syncAllAccounts: vi.fn(),
    listTransactions: vi.fn(),
    disconnectAccount: vi.fn(),
  },
}))

import { bankService } from '../../services/bank'

const mockAccount = {
  id: 'acct-uuid-1',
  provider: 'simplefin',
  provider_account_id: 'https://bridge.simplefin.org/simplefin/accounts/abc123',
  account_name: 'HSA Checking',
  account_type: 'depository',
  account_subtype: 'hsa',
  institution_name: 'First National Bank',
  last_four: null,
  currency: 'USD',
  is_active: true,
  last_synced_at: null,
  created_at: '2026-03-22T00:00:00',
  connection_status: 'connected' as const,
  connection_error: null,
}

const mockTransaction = {
  id: 'txn-uuid-1',
  connection_id: 'acct-uuid-1',
  provider: 'simplefin',
  provider_transaction_id: 'txn_001',
  transaction_date: '2026-03-01',
  description: 'CVS Pharmacy',
  amount: '-50.00',
  transaction_type: '',
  status: 'posted',
  details: null,
  created_at: '2026-03-22T00:00:00',
}

beforeEach(() => {
  vi.clearAllMocks()
  ;(bankService.listAccounts as any).mockResolvedValue([])
})

describe('BankAccounts page', () => {
  it('renders page title', async () => {
    render(<BankAccounts />)
    await waitFor(() => {
      expect(screen.getByText('Bank Accounts')).toBeInTheDocument()
    })
  })

  it('shows empty state when no accounts connected', async () => {
    render(<BankAccounts />)
    await waitFor(() => {
      expect(screen.getByText(/no bank accounts connected/i)).toBeInTheDocument()
    })
  })

  it('shows connect bank button', async () => {
    render(<BankAccounts />)
    await waitFor(() => {
      const btn = screen.getByRole('button', { name: /connect bank/i })
      expect(btn).not.toBeDisabled()
    })
  })

  it('renders connected accounts', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([mockAccount])
    render(<BankAccounts />)
    await waitFor(() => {
      expect(screen.getByText('HSA Checking')).toBeInTheDocument()
      expect(screen.getByText(/First National Bank/)).toBeInTheDocument()
    })
  })

  it('shows HSA badge for hsa subtype accounts', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([mockAccount])
    render(<BankAccounts />)
    await waitFor(() => {
      expect(screen.getByText('HSA')).toBeInTheDocument()
    })
  })

  it('shows transactions when account is clicked', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([mockAccount])
    ;(bankService.listTransactions as any).mockResolvedValue([mockTransaction])

    render(<BankAccounts />)
    await waitFor(() => screen.getByText('HSA Checking'))

    fireEvent.click(screen.getByText('HSA Checking'))

    await waitFor(() => {
      expect(screen.getByText('CVS Pharmacy')).toBeInTheDocument()
    })
    expect(bankService.listTransactions).toHaveBeenCalledWith('acct-uuid-1', { limit: 100 })
  })

  it('shows empty transactions message when none synced', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([mockAccount])
    ;(bankService.listTransactions as any).mockResolvedValue([])

    render(<BankAccounts />)
    await waitFor(() => screen.getByText('HSA Checking'))

    fireEvent.click(screen.getByText('HSA Checking'))

    await waitFor(() => {
      expect(screen.getByText(/no transactions synced/i)).toBeInTheDocument()
    })
  })

  it('formats negative amounts as debits', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([mockAccount])
    ;(bankService.listTransactions as any).mockResolvedValue([mockTransaction])

    render(<BankAccounts />)
    await waitFor(() => screen.getByText('HSA Checking'))
    fireEvent.click(screen.getByText('HSA Checking'))

    await waitFor(() => {
      expect(screen.getByText('-$50.00')).toBeInTheDocument()
    })
  })

  it('calls syncAccount when sync button is clicked', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([mockAccount])
    ;(bankService.syncAccount as any).mockResolvedValue({ added: 3, skipped: 0, account_id: 'acct-uuid-1' })

    render(<BankAccounts />)
    await waitFor(() => screen.getByText('HSA Checking'))

    const syncBtn = screen.getByRole('button', { name: /^sync$/i })
    fireEvent.click(syncBtn)

    await waitFor(() => {
      expect(bankService.syncAccount).toHaveBeenCalledWith('acct-uuid-1')
    })
  })

  it('shows error when account load fails', async () => {
    ;(bankService.listAccounts as any).mockRejectedValue(new Error('Network error'))

    render(<BankAccounts />)
    await waitFor(() => {
      expect(screen.getByText(/failed to load bank accounts/i)).toBeInTheDocument()
    })
  })

  it('shows select account prompt before any account is selected', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([mockAccount])
    render(<BankAccounts />)
    await waitFor(() => {
      expect(screen.getByText(/select an account to view transactions/i)).toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------------------
  // SimpleFIN connect flow
  // ---------------------------------------------------------------------------

  describe('connect modal', () => {
    it('opens connect modal when Connect Bank is clicked', async () => {
      render(<BankAccounts />)
      await waitFor(() => screen.getByRole('button', { name: /connect bank/i }))

      fireEvent.click(screen.getByRole('button', { name: /connect bank/i }))

      expect(screen.getByText(/connect via simplefin/i)).toBeInTheDocument()
      expect(screen.getByPlaceholderText(/setup token/i)).toBeInTheDocument()
    })

    it('closes connect modal when Cancel is clicked', async () => {
      render(<BankAccounts />)
      await waitFor(() => screen.getByRole('button', { name: /connect bank/i }))
      fireEvent.click(screen.getByRole('button', { name: /connect bank/i }))

      fireEvent.click(screen.getByRole('button', { name: /cancel/i }))

      expect(screen.queryByText(/connect via simplefin/i)).not.toBeInTheDocument()
    })

    it('calls bankService.connect with the setup token on submit', async () => {
      ;(bankService.connect as any).mockResolvedValue([mockAccount])

      render(<BankAccounts />)
      await waitFor(() => screen.getByRole('button', { name: /connect bank/i }))
      fireEvent.click(screen.getByRole('button', { name: /connect bank/i }))

      const textarea = screen.getByPlaceholderText(/setup token/i)
      fireEvent.change(textarea, { target: { value: 'aHR0cHM6Ly9leGFtcGxlLmNvbQ==' } })
      fireEvent.click(screen.getByRole('button', { name: /^connect$/i }))

      await waitFor(() => {
        expect(bankService.connect).toHaveBeenCalledWith('aHR0cHM6Ly9leGFtcGxlLmNvbQ==')
      })
    })

    it('shows error in modal when connect fails', async () => {
      const err = Object.assign(new Error('bad token'), {
        response: { data: { detail: 'Setup token has already been claimed or is invalid.' } },
      })
      ;(bankService.connect as any).mockRejectedValue(err)

      render(<BankAccounts />)
      await waitFor(() => screen.getByRole('button', { name: /connect bank/i }))
      fireEvent.click(screen.getByRole('button', { name: /connect bank/i }))

      const textarea = screen.getByPlaceholderText(/setup token/i)
      fireEvent.change(textarea, { target: { value: 'invalidtoken' } })
      fireEvent.click(screen.getByRole('button', { name: /^connect$/i }))

      await waitFor(() => {
        expect(screen.getByText(/setup token has already been claimed/i)).toBeInTheDocument()
      })
    })

    it('disables Connect button when textarea is empty', async () => {
      render(<BankAccounts />)
      await waitFor(() => screen.getByRole('button', { name: /connect bank/i }))
      fireEvent.click(screen.getByRole('button', { name: /connect bank/i }))

      expect(screen.getByRole('button', { name: /^connect$/i })).toBeDisabled()
    })
  })

  // ---------------------------------------------------------------------------
  // Connection health: badges
  // ---------------------------------------------------------------------------

  it('shows Disconnected badge on disconnected account', async () => {
    const disconnected = { ...mockAccount, id: 'acct-dis-1', connection_status: 'disconnected' as const }
    ;(bankService.listAccounts as any).mockResolvedValue([disconnected])
    render(<BankAccounts />)
    await waitFor(() => {
      expect(screen.getByText('Disconnected')).toBeInTheDocument()
    })
  })

  it('shows Sync Error badge on error account', async () => {
    const errored = { ...mockAccount, id: 'acct-err-1', connection_status: 'error' as const }
    ;(bankService.listAccounts as any).mockResolvedValue([errored])
    render(<BankAccounts />)
    await waitFor(() => {
      expect(screen.getByText('Sync Error')).toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------------------
  // Connection health: alert banner
  // ---------------------------------------------------------------------------

  it('shows reconnect alert banner when an account is disconnected', async () => {
    const disconnected = { ...mockAccount, id: 'acct-dis-2', account_name: 'Amex Gold', connection_status: 'disconnected' as const }
    ;(bankService.listAccounts as any).mockResolvedValue([disconnected])
    render(<BankAccounts />)
    await waitFor(() => {
      expect(screen.getByText(/needs to be reconnected/i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /re-connect/i })).toBeInTheDocument()
    })
  })

  it('does not show reconnect banner when all accounts are connected', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([mockAccount])
    render(<BankAccounts />)
    await waitFor(() => screen.getByText('HSA Checking'))
    expect(screen.queryByRole('button', { name: /re-connect/i })).not.toBeInTheDocument()
  })

  // ---------------------------------------------------------------------------
  // Connection health: sync button disabled on disconnected
  // ---------------------------------------------------------------------------

  it('disables sync button on disconnected account', async () => {
    const disconnected = { ...mockAccount, id: 'acct-dis-3', connection_status: 'disconnected' as const }
    ;(bankService.listAccounts as any).mockResolvedValue([disconnected])
    render(<BankAccounts />)
    await waitFor(() => {
      const syncBtn = screen.getByRole('button', { name: /^sync$/i })
      expect(syncBtn).toBeDisabled()
    })
  })

  // ---------------------------------------------------------------------------
  // Sync: specific error message
  // ---------------------------------------------------------------------------

  it('shows specific error detail on sync failure', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([mockAccount])
    const err = Object.assign(new Error('409'), {
      response: { data: { detail: 'SimpleFIN access URL is invalid or expired. Re-connect via the Connect Bank button.' } },
    })
    ;(bankService.syncAccount as any).mockRejectedValue(err)

    render(<BankAccounts />)
    await waitFor(() => screen.getByText('HSA Checking'))

    fireEvent.click(screen.getByRole('button', { name: /^sync$/i }))

    await waitFor(() => {
      expect(screen.getByText(/simplefin access url is invalid or expired/i)).toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------------------
  // Sync All
  // ---------------------------------------------------------------------------

  it('shows Sync All button', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([mockAccount])
    render(<BankAccounts />)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /sync all/i })).toBeInTheDocument()
    })
  })

  it('disables Sync All button when no connected accounts exist', async () => {
    const disconnected = { ...mockAccount, id: 'acct-dis-4', connection_status: 'disconnected' as const }
    ;(bankService.listAccounts as any).mockResolvedValue([disconnected])
    render(<BankAccounts />)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /sync all/i })).toBeDisabled()
    })
  })

  it('calls syncAllAccounts and shows result summary', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([mockAccount])
    ;(bankService.syncAllAccounts as any).mockResolvedValue({
      total: 1,
      succeeded: 1,
      failed: 0,
      outcomes: [{ account_id: 'acct-uuid-1', account_name: 'HSA Checking', status: 'ok', added: 3, skipped: 0, error: null }],
    })

    render(<BankAccounts />)
    await waitFor(() => screen.getByRole('button', { name: /sync all/i }))

    fireEvent.click(screen.getByRole('button', { name: /sync all/i }))

    await waitFor(() => {
      expect(bankService.syncAllAccounts).toHaveBeenCalled()
      expect(screen.getByText(/last bulk sync: 1\/1/i)).toBeInTheDocument()
    })
  })

  it('shows failed count in Sync All result when some accounts fail', async () => {
    const second = { ...mockAccount, id: 'acct-2', account_name: 'Amex', connection_status: 'connected' as const }
    ;(bankService.listAccounts as any).mockResolvedValue([mockAccount, second])
    ;(bankService.syncAllAccounts as any).mockResolvedValue({
      total: 2,
      succeeded: 1,
      failed: 1,
      outcomes: [],
    })

    render(<BankAccounts />)
    await waitFor(() => screen.getByRole('button', { name: /sync all/i }))
    fireEvent.click(screen.getByRole('button', { name: /sync all/i }))

    await waitFor(() => {
      expect(screen.getByText(/1 failed/i)).toBeInTheDocument()
    })
  })
})
