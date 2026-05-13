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
    getHistory: vi.fn(),
    listAutoInvestSchedules: vi.fn(),
    createAutoInvestSchedule: vi.fn(),
    updateAutoInvestSchedule: vi.fn(),
    deleteAutoInvestSchedule: vi.fn(),
    applyAutoInvest: vi.fn(),
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

const makeSchedule = (overrides = {}) => ({
  id: 'sched-1',
  account_id: 'acc-1',
  contribution_amount: '150.00',
  frequency: 'biweekly',
  next_contribution_date: '2099-01-01',
  is_active: true,
  is_due: false,
  allocations: [
    { id: 'alloc-1', holding_id: 'hold-1', ticker: 'VTI', percentage: '100.00' },
  ],
  created_at: '2026-01-01T00:00:00',
  updated_at: '2026-01-01T00:00:00',
  ...overrides,
})

beforeEach(() => {
  vi.clearAllMocks()
  ;(portfolioService.listAccounts as any).mockResolvedValue([])
  ;(portfolioService.getProjection as any).mockResolvedValue(emptyProjection)
  ;(portfolioService.refreshPrices as any).mockResolvedValue({ updated: 0, tickers_fetched: 0 })
  ;(portfolioService.createAccount as any).mockResolvedValue(makeAccount())
  ;(portfolioService.getHistory as any).mockResolvedValue({ points: [] })
  ;(portfolioService.listAutoInvestSchedules as any).mockResolvedValue([])
  ;(portfolioService.createAutoInvestSchedule as any).mockResolvedValue(makeSchedule())
  ;(portfolioService.applyAutoInvest as any).mockResolvedValue({
    applied_amount: '150.00',
    shares_added: [{ ticker: 'VTI', shares_added: '0.600000', price_used: '250.00', dollar_amount: '150.00' }],
    next_contribution_date: '2099-01-15',
  })
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

  it('clicking shares value enters edit mode with current value pre-filled', async () => {
    const account = makeAccount({ holdings: [makeHolding()] })
    ;(portfolioService.listAccounts as any).mockResolvedValue([account])
    render(<Portfolio />)
    await waitFor(() => screen.getByText('VTI'))

    fireEvent.click(screen.getByRole('button', { name: /edit shares for vti/i }))

    const input = screen.getByRole('spinbutton', { name: /shares for vti/i })
    expect(input).toBeInTheDocument()
    expect((input as HTMLInputElement).value).toBe('10')
  })

  it('saving shares edit calls updateHolding and updates the display', async () => {
    const account = makeAccount({ holdings: [makeHolding()] })
    const updatedHolding = makeHolding({ shares: '15.000000' })
    ;(portfolioService.listAccounts as any).mockResolvedValue([account])
    ;(portfolioService.updateHolding as any).mockResolvedValue(updatedHolding)
    render(<Portfolio />)
    await waitFor(() => screen.getByText('VTI'))

    fireEvent.click(screen.getByRole('button', { name: /edit shares for vti/i }))
    const input = screen.getByRole('spinbutton', { name: /shares for vti/i })
    fireEvent.change(input, { target: { value: '15' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(portfolioService.updateHolding).toHaveBeenCalledWith(
        'acc-1',
        'hold-1',
        expect.objectContaining({ shares: '15' })
      )
    })
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /edit shares for vti/i })).toHaveTextContent('15.0000')
    })
  })

  it('cancelling shares edit restores read-only display', async () => {
    const account = makeAccount({ holdings: [makeHolding()] })
    ;(portfolioService.listAccounts as any).mockResolvedValue([account])
    render(<Portfolio />)
    await waitFor(() => screen.getByText('VTI'))

    fireEvent.click(screen.getByRole('button', { name: /edit shares for vti/i }))
    expect(screen.getByRole('spinbutton', { name: /shares for vti/i })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('spinbutton', { name: /shares for vti/i })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /edit shares for vti/i })).toBeInTheDocument()
  })

  it('shows total portfolio value near the top when accounts exist', async () => {
    const account = makeAccount({ cash_balance: '500.00', holdings: [makeHolding()] })
    ;(portfolioService.listAccounts as any).mockResolvedValue([account])
    render(<Portfolio />)
    await waitFor(() => {
      // 10 shares × $250 + $500 cash = $3,000
      const totalEl = screen.getByTestId('portfolio-total')
      expect(totalEl).toHaveTextContent('$3,000.00')
    })
  })

  it('total portfolio value updates immediately after editing shares', async () => {
    const account = makeAccount({ cash_balance: '0.00', holdings: [makeHolding()] })
    const updatedHolding = makeHolding({ shares: '20.000000' })
    ;(portfolioService.listAccounts as any).mockResolvedValue([account])
    ;(portfolioService.updateHolding as any).mockResolvedValue(updatedHolding)
    render(<Portfolio />)
    await waitFor(() => screen.getByText('VTI'))

    // Initial: 10 shares × $250 = $2,500
    expect(screen.getByTestId('portfolio-total')).toHaveTextContent('$2,500.00')

    fireEvent.click(screen.getByRole('button', { name: /edit shares for vti/i }))
    const input = screen.getByRole('spinbutton', { name: /shares for vti/i })
    fireEvent.change(input, { target: { value: '20' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      // 20 shares × $250 = $5,000
      expect(screen.getByTestId('portfolio-total')).toHaveTextContent('$5,000.00')
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

describe('Auto-invest panel', () => {
  const accountWithHolding = makeAccount({ holdings: [makeHolding()] })

  beforeEach(() => {
    ;(portfolioService.listAccounts as any).mockResolvedValue([accountWithHolding])
  })

  it('shows "+ Set up schedule" when no schedules exist', async () => {
    ;(portfolioService.listAutoInvestSchedules as any).mockResolvedValue([])
    render(<Portfolio />)
    await waitFor(() => screen.getByText('My Fidelity HSA'))
    await waitFor(() => {
      expect(screen.getByText('+ Set up schedule')).toBeInTheDocument()
    })
  })

  it('shows the auto-invest form when setup link is clicked', async () => {
    ;(portfolioService.listAutoInvestSchedules as any).mockResolvedValue([])
    render(<Portfolio />)
    await waitFor(() => screen.getByText('+ Set up schedule'))
    fireEvent.click(screen.getByText('+ Set up schedule'))
    await waitFor(() => {
      expect(screen.getByTestId('auto-invest-form')).toBeInTheDocument()
    })
  })

  it('shows due contribution banner when is_due is true', async () => {
    ;(portfolioService.listAutoInvestSchedules as any).mockResolvedValue([
      makeSchedule({ is_due: true, next_contribution_date: '2026-01-01' }),
    ])
    render(<Portfolio />)
    await waitFor(() => screen.getByText('My Fidelity HSA'))
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /apply now/i })).toBeInTheDocument()
    })
  })

  it('calls applyAutoInvest and shows result message on apply', async () => {
    ;(portfolioService.listAutoInvestSchedules as any).mockResolvedValue([
      makeSchedule({ is_due: true }),
    ])
    render(<Portfolio />)
    await waitFor(() => screen.getByRole('button', { name: /apply now/i }))
    fireEvent.click(screen.getByRole('button', { name: /apply now/i }))
    await waitFor(() => {
      expect(portfolioService.applyAutoInvest).toHaveBeenCalledWith('sched-1')
      expect(screen.getByText(/applied \$150\.00/i)).toBeInTheDocument()
    })
  })

  it('shows active (non-due) schedule details', async () => {
    ;(portfolioService.listAutoInvestSchedules as any).mockResolvedValue([
      makeSchedule({ is_due: false, next_contribution_date: '2099-01-01' }),
    ])
    render(<Portfolio />)
    await waitFor(() => screen.getByText('My Fidelity HSA'))
    await waitFor(() => {
      expect(screen.getByText(/\$150\.00/)).toBeInTheDocument()
      expect(screen.getByText(/every 2 weeks/i)).toBeInTheDocument()
    })
  })
})

describe('Portfolio price auto-refresh', () => {
  it('auto-refreshes prices on mount when holdings have stale prices', async () => {
    const staleHolding = makeHolding({ last_price_fetched_at: '2020-01-01T00:00:00' })
    const staleAccount = makeAccount({ holdings: [staleHolding] })
    const freshAccount = makeAccount({ holdings: [makeHolding()] })

    ;(portfolioService.listAccounts as any)
      .mockResolvedValueOnce([staleAccount])
      .mockResolvedValueOnce([freshAccount])
    ;(portfolioService.listAutoInvestSchedules as any).mockResolvedValue([])

    render(<Portfolio />)

    await waitFor(() => {
      expect(portfolioService.refreshPrices).toHaveBeenCalled()
    })
  })

  it('does not auto-refresh when prices are fresh', async () => {
    const freshHolding = makeHolding({ last_price_fetched_at: new Date().toISOString() })
    const freshAccount = makeAccount({ holdings: [freshHolding] })

    ;(portfolioService.listAccounts as any).mockResolvedValue([freshAccount])
    ;(portfolioService.listAutoInvestSchedules as any).mockResolvedValue([])

    render(<Portfolio />)
    await waitFor(() => screen.getByText('My Fidelity HSA'))

    // Give async effects time to settle
    await new Promise(r => setTimeout(r, 50))
    expect(portfolioService.refreshPrices).not.toHaveBeenCalled()
  })

  it('does not auto-refresh when there are no holdings', async () => {
    ;(portfolioService.listAccounts as any).mockResolvedValue([makeAccount({ holdings: [] })])
    ;(portfolioService.listAutoInvestSchedules as any).mockResolvedValue([])

    render(<Portfolio />)
    await waitFor(() => screen.getByText('My Fidelity HSA'))

    await new Promise(r => setTimeout(r, 50))
    expect(portfolioService.refreshPrices).not.toHaveBeenCalled()
  })
})
