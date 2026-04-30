import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '../../test/utils'
import Dashboard from '../Dashboard'

vi.mock('../../services/bank', () => ({
  bankService: {
    getDashboardSummary: vi.fn(),
  },
}))

vi.mock('../../services/portfolio', () => ({
  portfolioService: {
    getSummary: vi.fn(),
    getHistory: vi.fn(),
  },
}))

import { bankService } from '../../services/bank'
import { portfolioService } from '../../services/portfolio'

const fullSummary = {
  hsa_spending: 0,
  pending_reimbursement: 0,
  hsa_transaction_count: 0,
  undocumented_hsa_count: 0,
  has_family_members: false,
  has_bank_connections: false,
  has_synced_transactions: false,
  has_hsa_transactions: false,
}

beforeEach(() => {
  vi.clearAllMocks()
  ;(bankService.getDashboardSummary as any).mockResolvedValue(fullSummary)
  ;(portfolioService.getSummary as any).mockResolvedValue({ total_value: null, accounts: [] })
  ;(portfolioService.getHistory as any).mockResolvedValue({ points: [] })
})

describe('Dashboard', () => {
  it('renders the hero section labels', async () => {
    render(<Dashboard />)
    expect(screen.getByText('Lifetime HSA Spend')).toBeInTheDocument()
    expect(screen.getByText('Portfolio Value')).toBeInTheDocument()
  })

  it('shows lifetime HSA spend from the all-time API call', async () => {
    ;(bankService.getDashboardSummary as any).mockResolvedValue({
      ...fullSummary,
      hsa_spending: 1500.00,
      hsa_transaction_count: 12,
    })
    render(<Dashboard />)
    await waitFor(() => {
      expect(screen.getAllByText('$1,500.00').length).toBeGreaterThanOrEqual(1)
      expect(screen.getByText('12 expenses')).toBeInTheDocument()
    })
  })

  it('shows portfolio value in the hero when available', async () => {
    ;(portfolioService.getSummary as any).mockResolvedValue({
      total_value: '8250.50',
      accounts: [{ id: '1' }],
    })
    render(<Dashboard />)
    await waitFor(() => {
      expect(screen.getByText('$8,250.50')).toBeInTheDocument()
      expect(screen.getByTestId('portfolio-link')).toBeInTheDocument()
    })
  })

  it('shows set-up link in hero when no portfolio accounts', async () => {
    render(<Dashboard />)
    await waitFor(() => {
      expect(screen.getByTestId('portfolio-setup-link')).toBeInTheDocument()
    })
  })

  it('shows all time-range buttons', async () => {
    render(<Dashboard />)
    for (const label of ['1D', '1W', '1M', '3M', '6M', 'YTD', '1Y', '2Y', '5Y', '10Y', 'ALL']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
  })

  it('defaults to YTD range and passes start_date to API', async () => {
    render(<Dashboard />)
    await waitFor(() => {
      expect(bankService.getDashboardSummary).toHaveBeenCalledWith(
        expect.objectContaining({ start_date: expect.stringMatching(/^\d{4}-01-01$/) })
      )
    })
  })

  it('passes no start_date when ALL range is selected', async () => {
    render(<Dashboard />)
    await waitFor(() => screen.getByRole('button', { name: 'ALL' }))

    screen.getByRole('button', { name: 'ALL' }).click()

    await waitFor(() => {
      const calls = (bankService.getDashboardSummary as any).mock.calls
      const lastCall = calls[calls.length - 1][0]
      expect(lastCall.start_date).toBeUndefined()
    })
  })

  it('shows stat card labels', async () => {
    render(<Dashboard />)
    await waitFor(() => {
      expect(screen.getByText('HSA Spending')).toBeInTheDocument()
      expect(screen.getByText('Pending Reimbursement')).toBeInTheDocument()
      expect(screen.getByText('HSA Transactions')).toBeInTheDocument()
      expect(screen.getByText('Needs Documentation')).toBeInTheDocument()
    })
  })

  it('displays formatted spending from API', async () => {
    ;(bankService.getDashboardSummary as any).mockResolvedValue({
      ...fullSummary,
      hsa_spending: 250.75,
      hsa_transaction_count: 3,
    })
    render(<Dashboard />)
    await waitFor(() => {
      // $250.75 appears in both the lifetime hero and the period card (same mock)
      expect(screen.getAllByText('$250.75').length).toBeGreaterThanOrEqual(1)
      expect(screen.getByText(/3 flagged transactions/i)).toBeInTheDocument()
    })
  })

  it('shows getting started checklist when setup is incomplete', async () => {
    render(<Dashboard />)
    await waitFor(() => {
      expect(screen.getByText('Getting Started')).toBeInTheDocument()
      expect(screen.getByText('Add family members')).toBeInTheDocument()
      expect(screen.getByText('Connect a bank account')).toBeInTheDocument()
      expect(screen.getByText('Sync transactions')).toBeInTheDocument()
      expect(screen.getByText('Flag HSA transactions')).toBeInTheDocument()
    })
  })

  it('hides checklist when all setup steps are complete', async () => {
    ;(bankService.getDashboardSummary as any).mockResolvedValue({
      ...fullSummary,
      has_family_members: true,
      has_bank_connections: true,
      has_synced_transactions: true,
      has_hsa_transactions: true,
    })
    render(<Dashboard />)
    await waitFor(() => {
      expect(screen.queryByText('Getting Started')).not.toBeInTheDocument()
    })
  })

  it('shows completed steps as struck-through', async () => {
    ;(bankService.getDashboardSummary as any).mockResolvedValue({
      ...fullSummary,
      has_family_members: true,
    })
    render(<Dashboard />)
    await waitFor(() => {
      const step = screen.getByText('Add family members')
      expect(step.className).toContain('line-through')
    })
  })

  it('has link to HSA transactions tab', async () => {
    render(<Dashboard />)
    await waitFor(() => {
      const link = screen.getByText(/view HSA transactions/i)
      expect(link.closest('a')).toHaveAttribute('href', '/transactions?tab=hsa')
    })
  })

  it('shows "why waiting pays off" tip link when pending_reimbursement > 0', async () => {
    ;(bankService.getDashboardSummary as any).mockResolvedValue({
      ...fullSummary,
      pending_reimbursement: 150.00,
    })
    render(<Dashboard />)
    await waitFor(() => {
      const link = screen.getByTestId('pending-reimburse-tip')
      expect(link).toBeInTheDocument()
      expect(link.closest('a')).toHaveAttribute('href', '/transactions?tab=reimbursed')
    })
  })

  it('does not show the tip link when pending_reimbursement is 0', async () => {
    render(<Dashboard />)
    await waitFor(() => expect(screen.getByText('All caught up!')).toBeInTheDocument())
    expect(screen.queryByTestId('pending-reimburse-tip')).not.toBeInTheDocument()
  })

  describe('Needs Documentation card', () => {
    it('shows 0 and all-documented message when count is 0', async () => {
      render(<Dashboard />)
      await waitFor(() => {
        expect(screen.getByText('All HSA expenses documented')).toBeInTheDocument()
      })
    })

    it('shows attach link pointing to HSA tab with missing-docs filter', async () => {
      ;(bankService.getDashboardSummary as any).mockResolvedValue({
        ...fullSummary,
        undocumented_hsa_count: 7,
      })
      render(<Dashboard />)
      await waitFor(() => {
        const link = screen.getByText(/attach receipts/i)
        expect(link.closest('a')).toHaveAttribute('href', '/transactions?tab=hsa&docs=missing')
      })
    })

    it('uses amber styling when undocumented count is greater than 0', async () => {
      ;(bankService.getDashboardSummary as any).mockResolvedValue({
        ...fullSummary,
        undocumented_hsa_count: 7,
      })
      render(<Dashboard />)
      await waitFor(() => {
        const count = screen.getByText('7')
        expect(count.className).toContain('text-amber-600')
      })
    })
  })
})
