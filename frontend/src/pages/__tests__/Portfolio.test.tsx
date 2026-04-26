import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '../../test/utils'
import Portfolio from '../Portfolio'

vi.mock('../../services/portfolio', () => ({
  portfolioService: {
    listAccounts: vi.fn(),
    createAccount: vi.fn(),
    updateAccount: vi.fn(),
    deleteAccount: vi.fn(),
    listHoldings: vi.fn(),
    addHolding: vi.fn(),
    updateHolding: vi.fn(),
    deleteHolding: vi.fn(),
    refreshPrices: vi.fn(),
    getSummary: vi.fn(),
    getProjection: vi.fn(),
  },
}))

import { portfolioService } from '../../services/portfolio'

const makeAccount = (overrides = {}) => ({
  id: 'acc-1',
  user_id: 'user-1',
  institution_name: 'Fidelity',
  nickname: 'My Fidelity HSA',
  account_type: 'investment' as const,
  is_active: true,
  cash_balance: '500.00',
  cash_balance_updated_at: null,
  last_checkin_at: null,
  holdings: [],
  created_at: '2026-01-01T00:00:00',
  updated_at: '2026-01-01T00:00:00',
  ...overrides,
})

const makeHolding = (overrides = {}) => ({
  id: 'hold-1',
  account_id: 'acc-1',
  ticker: 'VTI',
  shares: '10.000000',
  last_known_price: '250.00',
  last_price_fetched_at: '2026-04-20T10:00:00',
  created_at: '2026-01-01T00:00:00',
  updated_at: '2026-04-20T10:00:00',
  ...overrides,
})

const emptyProjection = {
  starting_value: '0.00',
  annual_return: 7,
  points: [{ year: 0, value: '0.00' }],
}

beforeEach(() => {
  vi.clearAllMocks()
  ;(portfolioService.listAccounts as any).mockResolvedValue([])
  ;(portfolioService.getProjection as any).mockResolvedValue(emptyProjection)
  ;(portfolioService.refreshPrices as any).mockResolvedValue({ updated: 0, tickers_fetched: 0 })
  ;(portfolioService.createAccount as any).mockResolvedValue(makeAccount())
})

describe('Portfolio page', () => {
  it('renders page title', async () => {
    render(<Portfolio />)
    expect(screen.getByText('HSA Portfolio')).toBeInTheDocument()
  })

  it('shows empty state when no accounts', async () => {
    render(<Portfolio />)
    await waitFor(() => {
      expect(screen.getByText(/no hsa accounts yet/i)).toBeInTheDocument()
    })
  })

  it('renders account card with institution name', async () => {
    ;(portfolioService.listAccounts as any).mockResolvedValue([makeAccount()])
    render(<Portfolio />)
    await waitFor(() => {
      expect(screen.getByText('My Fidelity HSA')).toBeInTheDocument()
      expect(screen.getByText('Fidelity')).toBeInTheDocument()
    })
  })

  it('renders holding ticker and shares in account card', async () => {
    const account = makeAccount({ holdings: [makeHolding()] })
    ;(portfolioService.listAccounts as any).mockResolvedValue([account])
    render(<Portfolio />)
    await waitFor(() => {
      expect(screen.getByText('VTI')).toBeInTheDocument()
    })
  })

  it('"Update prices" button calls refreshPrices', async () => {
    ;(portfolioService.listAccounts as any).mockResolvedValue([makeAccount()])
    render(<Portfolio />)
    await waitFor(() => screen.getByText('My Fidelity HSA'))
    fireEvent.click(screen.getByRole('button', { name: /update prices/i }))
    await waitFor(() => {
      expect(portfolioService.refreshPrices).toHaveBeenCalled()
    })
  })

  it('shows invested value after price refresh updates account holdings', async () => {
    const accountWithoutPrices = makeAccount({ holdings: [makeHolding({ last_known_price: null })] })
    const accountWithPrices = makeAccount({ holdings: [makeHolding({ last_known_price: '250.00' })] })

    ;(portfolioService.listAccounts as any)
      .mockResolvedValueOnce([accountWithoutPrices])
      .mockResolvedValueOnce([accountWithPrices])
    ;(portfolioService.refreshPrices as any).mockResolvedValue({ updated: 1, tickers_fetched: 1 })

    render(<Portfolio />)
    await waitFor(() => screen.getByText('My Fidelity HSA'))

    fireEvent.click(screen.getByRole('button', { name: /update prices/i }))

    await waitFor(() => {
      // 10 shares × $250 = $2,500 invested (may appear in both holdings row and summary)
      expect(screen.getAllByText('$2,500.00').length).toBeGreaterThan(0)
    })
  })

  it('shows add account form when "+ Add account" is clicked', async () => {
    render(<Portfolio />)
    await waitFor(() => expect(portfolioService.listAccounts).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('button', { name: /\+ add account/i }))
    await waitFor(() => {
      expect(screen.getByTestId('add-account-form')).toBeInTheDocument()
    })
  })

  it('add account form submission calls createAccount', async () => {
    render(<Portfolio />)
    await waitFor(() => expect(portfolioService.listAccounts).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('button', { name: /\+ add account/i }))
    await waitFor(() => screen.getByTestId('add-account-form'))

    const form = screen.getByTestId('add-account-form')
    fireEvent.change(within(form).getByPlaceholderText(/fidelity, rippling/i), {
      target: { value: 'Schwab' },
    })
    fireEvent.click(within(form).getByRole('button', { name: /add account/i }))

    await waitFor(() => {
      expect(portfolioService.createAccount).toHaveBeenCalledWith(
        expect.objectContaining({ institution_name: 'Schwab' })
      )
    })
  })

  it('projection table renders rows when accounts exist', async () => {
    ;(portfolioService.listAccounts as any).mockResolvedValue([makeAccount()])
    ;(portfolioService.getProjection as any).mockResolvedValue({
      starting_value: '500.00',
      annual_return: 7,
      points: [
        { year: 0, value: '500.00' },
        { year: 1, value: '535.00' },
        { year: 5, value: '701.28' },
        { year: 10, value: '983.58' },
        { year: 20, value: '1934.30' },
      ],
    })
    render(<Portfolio />)
    await waitFor(() => screen.getByText('My Fidelity HSA'))
    await waitFor(() => {
      expect(screen.getByText('Growth Projection')).toBeInTheDocument()
      expect(screen.getByText('Year 1')).toBeInTheDocument()
    })
  })
})
