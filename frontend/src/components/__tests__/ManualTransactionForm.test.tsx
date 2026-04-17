import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '../../test/utils'
import ManualTransactionForm from '../ManualTransactionForm'

vi.mock('../../services/bank', () => ({
  bankService: {
    findMatchingTransactions: vi.fn(),
    createManualTransaction: vi.fn(),
  },
}))

import { bankService } from '../../services/bank'

const makeMatch = (overrides = {}) => ({
  id: 'txn-1',
  transaction_date: '2026-03-15',
  amount: '50.00',
  merchant_name: 'WALGREENS',
  description: null,
  teller_category: 'health_and_wellness',
  ...overrides,
})

const makeTxn = (overrides = {}) => ({
  id: 'txn-new',
  source: 'manual',
  transaction_date: '2026-03-15',
  amount: '-50.00',
  description: null,
  connection_id: null,
  provider: 'manual',
  provider_transaction_id: 'manual-abc',
  transaction_type: 'manual',
  status: 'posted',
  details: {},
  created_at: '2026-03-15T00:00:00',
  is_hsa_eligible: null,
  family_member_id: null,
  hsa_category: null,
  eligible_amount: null,
  reimbursement_status: null,
  reimbursed_at: null,
  notes: null,
  account_name: null,
  institution_name: null,
  document_count: 0,
  auto_flag: null,
  rule_id: null,
  eligibility_warning: false,
  teller_category: null,
  ...overrides,
})

beforeEach(() => {
  vi.clearAllMocks()
  ;(bankService.findMatchingTransactions as any).mockResolvedValue([])
  ;(bankService.createManualTransaction as any).mockResolvedValue(makeTxn())
})

const fillForm = (overrides: { date?: string; amount?: string; merchant?: string } = {}) => {
  fireEvent.change(screen.getByLabelText('Date'), {
    target: { value: overrides.date ?? '2026-03-15' },
  })
  fireEvent.change(screen.getByLabelText('Amount ($)'), {
    target: { value: overrides.amount ?? '50.00' },
  })
  fireEvent.change(screen.getByLabelText('Merchant'), {
    target: { value: overrides.merchant ?? 'Dr. Jones' },
  })
}

describe('ManualTransactionForm', () => {
  it('renders the form fields', () => {
    render(<ManualTransactionForm onClose={() => {}} onCreated={() => {}} />)
    expect(screen.getByLabelText('Date')).toBeInTheDocument()
    expect(screen.getByLabelText('Amount ($)')).toBeInTheDocument()
    expect(screen.getByLabelText('Merchant')).toBeInTheDocument()
    expect(screen.getByLabelText(/description/i)).toBeInTheDocument()
  })

  it('calls onClose when Cancel is clicked', () => {
    const onClose = vi.fn()
    render(<ManualTransactionForm onClose={onClose} onCreated={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onClose).toHaveBeenCalled()
  })

  describe('no duplicates found', () => {
    it('calls createManualTransaction and onCreated on submit', async () => {
      const onCreated = vi.fn()
      render(<ManualTransactionForm onClose={() => {}} onCreated={onCreated} />)
      fillForm()
      fireEvent.click(screen.getByRole('button', { name: 'Add transaction' }))

      await waitFor(() => {
        expect(bankService.findMatchingTransactions).toHaveBeenCalledWith(
          expect.objectContaining({ amount: '50.00', date: '2026-03-15', merchant: 'Dr. Jones' })
        )
        expect(bankService.createManualTransaction).toHaveBeenCalled()
        expect(onCreated).toHaveBeenCalled()
      })
    })
  })

  describe('duplicate detection', () => {
    it('shows possible duplicate panel when matches are found', async () => {
      ;(bankService.findMatchingTransactions as any).mockResolvedValue([makeMatch()])
      render(<ManualTransactionForm onClose={() => {}} onCreated={() => {}} />)
      fillForm()
      fireEvent.click(screen.getByRole('button', { name: 'Add transaction' }))

      await waitFor(() => {
        expect(screen.getByText('Possible duplicate found')).toBeInTheDocument()
        expect(screen.getByText('WALGREENS')).toBeInTheDocument()
      })
      expect(bankService.createManualTransaction).not.toHaveBeenCalled()
    })

    it('"Already in my data" cancels creation', async () => {
      ;(bankService.findMatchingTransactions as any).mockResolvedValue([makeMatch()])
      const onClose = vi.fn()
      render(<ManualTransactionForm onClose={onClose} onCreated={() => {}} />)
      fillForm()
      fireEvent.click(screen.getByRole('button', { name: 'Add transaction' }))

      await waitFor(() => screen.getByText('Possible duplicate found'))
      fireEvent.click(screen.getByRole('button', { name: /already in my data/i }))

      expect(bankService.createManualTransaction).not.toHaveBeenCalled()
      expect(onClose).toHaveBeenCalled()
    })

    it('"Not the same" proceeds with creation', async () => {
      const onCreated = vi.fn()
      ;(bankService.findMatchingTransactions as any).mockResolvedValue([makeMatch()])
      render(<ManualTransactionForm onClose={() => {}} onCreated={onCreated} />)
      fillForm()
      fireEvent.click(screen.getByRole('button', { name: 'Add transaction' }))

      await waitFor(() => screen.getByText('Possible duplicate found'))
      fireEvent.click(screen.getByRole('button', { name: /not the same/i }))

      await waitFor(() => {
        expect(bankService.createManualTransaction).toHaveBeenCalled()
        expect(onCreated).toHaveBeenCalled()
      })
    })
  })

  describe('error handling', () => {
    it('shows error when match check fails', async () => {
      ;(bankService.findMatchingTransactions as any).mockRejectedValue(new Error('network'))
      render(<ManualTransactionForm onClose={() => {}} onCreated={() => {}} />)
      fillForm()
      fireEvent.click(screen.getByRole('button', { name: 'Add transaction' }))

      await waitFor(() => {
        expect(screen.getByText('Something went wrong. Please try again.')).toBeInTheDocument()
      })
    })

    it('shows error when create fails', async () => {
      ;(bankService.createManualTransaction as any).mockRejectedValue(new Error('server'))
      render(<ManualTransactionForm onClose={() => {}} onCreated={() => {}} />)
      fillForm()
      fireEvent.click(screen.getByRole('button', { name: 'Add transaction' }))

      await waitFor(() => {
        expect(screen.getByText('Failed to create transaction. Please try again.')).toBeInTheDocument()
      })
    })
  })
})
