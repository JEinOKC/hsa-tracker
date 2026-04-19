import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '../../test/utils'
import ReviewQueue from '../ReviewQueue'

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('../../services/bank', () => ({
  bankService: {
    listAllTransactions: vi.fn(),
    annotateTransaction: vi.fn(),
  },
}))

import { bankService } from '../../services/bank'

function makeTxn(overrides = {}) {
  return {
    id: 'txn-1',
    transaction_date: '2026-04-01',
    description: 'CVS Pharmacy',
    counterparty_name: 'CVS',
    amount: '-42.00',
    is_hsa_eligible: null,
    auto_flag: 'potential_hsa',
    hsa_category: null,
    rule_id: null,
    status: 'posted',
    institution_name: 'Chase',
    document_count: 0,
    eligibility_warning: false,
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
  ;(bankService.annotateTransaction as any).mockResolvedValue({})
})

describe('ReviewQueue', () => {
  it('shows the first unreviewed transaction', async () => {
    render(<ReviewQueue />)
    await waitFor(() => {
      expect(screen.getByText('CVS Pharmacy')).toBeInTheDocument()
      expect(screen.getByText('$42.00')).toBeInTheDocument()
    })
  })

  it('shows progress counter', async () => {
    render(<ReviewQueue />)
    await waitFor(() => {
      expect(screen.getByText('1 of 1')).toBeInTheDocument()
    })
  })

  it('HSA Eligible button calls annotateTransaction with true and advances', async () => {
    ;(bankService.listAllTransactions as any).mockResolvedValue([
      makeTxn({ id: 'txn-1' }),
      makeTxn({ id: 'txn-2', description: 'Walgreens' }),
    ])

    render(<ReviewQueue />)
    await waitFor(() => screen.getByText('CVS Pharmacy'))

    fireEvent.click(screen.getByRole('button', { name: /hsa eligible/i }))

    await waitFor(() => {
      expect(bankService.annotateTransaction).toHaveBeenCalledWith('txn-1', { is_hsa_eligible: true })
      expect(screen.getByText('Walgreens')).toBeInTheDocument()
    })
  })

  it('Not HSA button calls annotateTransaction with false and advances', async () => {
    ;(bankService.listAllTransactions as any).mockResolvedValue([
      makeTxn({ id: 'txn-1' }),
      makeTxn({ id: 'txn-2', description: 'Walgreens' }),
    ])

    render(<ReviewQueue />)
    await waitFor(() => screen.getByText('CVS Pharmacy'))

    fireEvent.click(screen.getByRole('button', { name: /not hsa/i }))

    await waitFor(() => {
      expect(bankService.annotateTransaction).toHaveBeenCalledWith('txn-1', { is_hsa_eligible: false })
      expect(screen.getByText('Walgreens')).toBeInTheDocument()
    })
  })

  it('Skip advances without calling annotateTransaction', async () => {
    ;(bankService.listAllTransactions as any).mockResolvedValue([
      makeTxn({ id: 'txn-1' }),
      makeTxn({ id: 'txn-2', description: 'Walgreens' }),
    ])

    render(<ReviewQueue />)
    await waitFor(() => screen.getByText('CVS Pharmacy'))

    fireEvent.click(screen.getByRole('button', { name: /skip/i }))

    await waitFor(() => {
      expect(bankService.annotateTransaction).not.toHaveBeenCalled()
      expect(screen.getByText('Walgreens')).toBeInTheDocument()
    })
  })

  it('shows All caught up when queue is empty', async () => {
    ;(bankService.listAllTransactions as any).mockResolvedValue([])

    render(<ReviewQueue />)
    await waitFor(() => {
      expect(screen.getByText(/all caught up/i)).toBeInTheDocument()
    })
  })

  it('filters out already-reviewed transactions', async () => {
    ;(bankService.listAllTransactions as any).mockResolvedValue([
      makeTxn({ id: 'txn-reviewed', is_hsa_eligible: true }),
    ])

    render(<ReviewQueue />)
    await waitFor(() => {
      expect(screen.getByText(/all caught up/i)).toBeInTheDocument()
    })
  })

  it('shows All caught up after reviewing the last item', async () => {
    render(<ReviewQueue />)
    await waitFor(() => screen.getByText('CVS Pharmacy'))

    fireEvent.click(screen.getByRole('button', { name: /hsa eligible/i }))

    await waitFor(() => {
      expect(screen.getByText(/all caught up/i)).toBeInTheDocument()
    })
  })

  it('Done Reviewing button navigates to /transactions?tab=hsa', async () => {
    render(<ReviewQueue />)
    await waitFor(() => screen.getByText(/done reviewing/i))

    fireEvent.click(screen.getByText(/done reviewing/i))
    expect(mockNavigate).toHaveBeenCalledWith('/transactions?tab=hsa')
  })
})
