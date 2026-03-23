import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '../../test/utils'
import userEvent from '@testing-library/user-event'
import Transactions from '../Transactions'

vi.mock('../../services/bank', () => ({
  bankService: {
    listAllTransactions: vi.fn(),
    annotateTransaction: vi.fn(),
  },
  HSA_CATEGORIES: [
    { value: 'medical', label: 'Medical Care' },
    { value: 'dental', label: 'Dental Care' },
    { value: 'vision', label: 'Vision Care' },
  ],
}))

vi.mock('../../services/family', () => ({
  familyService: {
    list: vi.fn(),
  },
}))

import { bankService } from '../../services/bank'
import { familyService } from '../../services/family'

const makeTxn = (overrides = {}) => ({
  id: 'txn-1',
  connection_id: 'conn-1',
  provider: 'teller',
  provider_transaction_id: 'p_txn_1',
  transaction_date: '2026-03-01',
  description: 'CVS Pharmacy',
  amount: '-42.00',
  transaction_type: 'card_payment',
  status: 'posted',
  details: null,
  created_at: '2026-03-22T00:00:00',
  is_hsa_eligible: null,
  family_member_id: null,
  hsa_category: null,
  reimbursement_status: null,
  notes: null,
  account_name: 'HSA Checking',
  institution_name: 'First Bank',
  ...overrides,
})

const mockMember = {
  id: 'member-1',
  user_id: 'user-1',
  name: 'Jane',
  member_relationship: 'spouse',
  date_of_birth: null,
}

beforeEach(() => {
  vi.clearAllMocks()
  ;(bankService.listAllTransactions as any).mockResolvedValue([])
  ;(familyService.list as any).mockResolvedValue([])
})

describe('Transactions page', () => {
  it('renders page title', async () => {
    render(<Transactions />)
    await waitFor(() => {
      expect(screen.getByText('Transactions')).toBeInTheDocument()
    })
  })

  it('shows All Transactions and HSA Transactions tabs', async () => {
    render(<Transactions />)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'All Transactions' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'HSA Transactions' })).toBeInTheDocument()
    })
  })

  it('loads transactions on mount', async () => {
    ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
    render(<Transactions />)
    await waitFor(() => {
      expect(bankService.listAllTransactions).toHaveBeenCalledWith(
        expect.objectContaining({ limit: 500 })
      )
    })
  })

  it('loads family members on mount', async () => {
    render(<Transactions />)
    await waitFor(() => {
      expect(familyService.list).toHaveBeenCalled()
    })
  })

  it('shows transaction description and amount', async () => {
    ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
    render(<Transactions />)
    await waitFor(() => {
      expect(screen.getByText('CVS Pharmacy')).toBeInTheDocument()
      expect(screen.getByText('-$42.00')).toBeInTheDocument()
    })
  })

  it('shows institution and account name in description cell', async () => {
    ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
    render(<Transactions />)
    await waitFor(() => {
      expect(screen.getByText(/First Bank/)).toBeInTheDocument()
    })
  })

  it('shows empty state for all-transactions tab', async () => {
    render(<Transactions />)
    await waitFor(() => {
      expect(screen.getByText(/no transactions found/i)).toBeInTheDocument()
    })
  })

  it('shows error message when load fails', async () => {
    ;(bankService.listAllTransactions as any).mockRejectedValue(new Error('Network error'))
    render(<Transactions />)
    await waitFor(() => {
      expect(screen.getByText(/failed to load transactions/i)).toBeInTheDocument()
    })
  })

  it('shows transaction count in footer', async () => {
    ;(bankService.listAllTransactions as any).mockResolvedValue([
      makeTxn({ id: 'txn-1' }),
      makeTxn({ id: 'txn-2', description: 'Walgreens' }),
    ])
    render(<Transactions />)
    await waitFor(() => {
      expect(screen.getByText(/2 transactions/i)).toBeInTheDocument()
    })
  })

  describe('tab switching', () => {
    it('defaults to All Transactions tab', async () => {
      render(<Transactions />)
      await waitFor(() => {
        const allTab = screen.getByRole('button', { name: 'All Transactions' })
        expect(allTab.className).toContain('border-blue-600')
      })
    })

    it('switches to HSA tab and reloads with is_hsa_eligible filter', async () => {
      render(<Transactions />)
      await waitFor(() => screen.getByRole('button', { name: 'HSA Transactions' }))

      fireEvent.click(screen.getByRole('button', { name: 'HSA Transactions' }))

      await waitFor(() => {
        expect(bankService.listAllTransactions).toHaveBeenCalledWith(
          expect.objectContaining({ is_hsa_eligible: true })
        )
      })
    })

    it('shows empty state for HSA tab with specific message', async () => {
      render(<Transactions />)
      await waitFor(() => screen.getByRole('button', { name: 'HSA Transactions' }))

      fireEvent.click(screen.getByRole('button', { name: 'HSA Transactions' }))

      await waitFor(() => {
        expect(screen.getByText(/no HSA transactions yet/i)).toBeInTheDocument()
      })
    })

    it('shows HSA total on HSA tab', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ id: 'txn-1', is_hsa_eligible: true, amount: '-42.00' }),
      ])
      render(<Transactions />)
      await waitFor(() => screen.getByRole('button', { name: 'HSA Transactions' }))

      fireEvent.click(screen.getByRole('button', { name: 'HSA Transactions' }))

      await waitFor(() => {
        expect(screen.getByText('HSA total')).toBeInTheDocument()
      })
    })

    it('does not show HSA total on All tab', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
      render(<Transactions />)
      await waitFor(() => {
        expect(screen.queryByText('HSA total')).not.toBeInTheDocument()
      })
    })

    it('shows Category column header only on HSA tab', async () => {
      render(<Transactions />)
      await waitFor(() => screen.getByRole('button', { name: 'HSA Transactions' }))

      expect(screen.queryByText('Category')).not.toBeInTheDocument()

      fireEvent.click(screen.getByRole('button', { name: 'HSA Transactions' }))

      await waitFor(() => {
        expect(screen.getByText('Category')).toBeInTheDocument()
      })
    })
  })

  describe('HsaToggle', () => {
    it('shows Mark button for unreviewed transaction (null)', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn({ is_hsa_eligible: null })])
      render(<Transactions />)
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Mark' })).toBeInTheDocument()
      })
    })

    it('shows HSA button for eligible transaction', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn({ is_hsa_eligible: true })])
      render(<Transactions />)
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'HSA' })).toBeInTheDocument()
      })
    })

    it('shows Not HSA button for ineligible transaction', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn({ is_hsa_eligible: false })])
      render(<Transactions />)
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Not HSA' })).toBeInTheDocument()
      })
    })

    it('calls annotateTransaction with true when Mark is clicked', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn({ is_hsa_eligible: null })])
      ;(bankService.annotateTransaction as any).mockResolvedValue(makeTxn({ is_hsa_eligible: true }))

      render(<Transactions />)
      await waitFor(() => screen.getByRole('button', { name: 'Mark' }))

      fireEvent.click(screen.getByRole('button', { name: 'Mark' }))

      await waitFor(() => {
        expect(bankService.annotateTransaction).toHaveBeenCalledWith('txn-1', { is_hsa_eligible: true })
      })
    })

    it('calls annotateTransaction with false when HSA button is clicked', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn({ is_hsa_eligible: true })])
      ;(bankService.annotateTransaction as any).mockResolvedValue(makeTxn({ is_hsa_eligible: false }))

      render(<Transactions />)
      await waitFor(() => screen.getByRole('button', { name: 'HSA' }))

      fireEvent.click(screen.getByRole('button', { name: 'HSA' }))

      await waitFor(() => {
        expect(bankService.annotateTransaction).toHaveBeenCalledWith('txn-1', { is_hsa_eligible: false })
      })
    })

    it('calls annotateTransaction with null when Not HSA button is clicked', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn({ is_hsa_eligible: false })])
      ;(bankService.annotateTransaction as any).mockResolvedValue(makeTxn({ is_hsa_eligible: null }))

      render(<Transactions />)
      await waitFor(() => screen.getByRole('button', { name: 'Not HSA' }))

      fireEvent.click(screen.getByRole('button', { name: 'Not HSA' }))

      await waitFor(() => {
        expect(bankService.annotateTransaction).toHaveBeenCalledWith('txn-1', { is_hsa_eligible: null })
      })
    })

    it('updates row state after annotation without full reload', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn({ is_hsa_eligible: null })])
      ;(bankService.annotateTransaction as any).mockResolvedValue(makeTxn({ is_hsa_eligible: true }))

      render(<Transactions />)
      await waitFor(() => screen.getByRole('button', { name: 'Mark' }))

      fireEvent.click(screen.getByRole('button', { name: 'Mark' }))

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'HSA' })).toBeInTheDocument()
      })
      // listAllTransactions should only have been called once (on mount)
      expect(bankService.listAllTransactions).toHaveBeenCalledTimes(1)
    })
  })

  describe('MemberPicker', () => {
    it('shows family members in person picker dropdown', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
      ;(familyService.list as any).mockResolvedValue([mockMember])

      render(<Transactions />)
      await waitFor(() => {
        // Both the filter bar and per-row picker show Jane — at least one must exist
        const janeOptions = screen.getAllByRole('option', { name: 'Jane' })
        expect(janeOptions.length).toBeGreaterThanOrEqual(1)
      })
    })

    it('calls annotateTransaction with family_member_id when member is selected', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
      ;(familyService.list as any).mockResolvedValue([mockMember])
      ;(bankService.annotateTransaction as any).mockResolvedValue(
        makeTxn({ family_member_id: 'member-1' })
      )

      render(<Transactions />)
      await waitFor(() => screen.getByDisplayValue('— person —'))

      fireEvent.change(screen.getByDisplayValue('— person —'), { target: { value: 'member-1' } })

      await waitFor(() => {
        expect(bankService.annotateTransaction).toHaveBeenCalledWith('txn-1', { family_member_id: 'member-1' })
      })
    })

    it('calls annotateTransaction with null when person is cleared', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ family_member_id: 'member-1' }),
      ])
      ;(familyService.list as any).mockResolvedValue([mockMember])
      ;(bankService.annotateTransaction as any).mockResolvedValue(makeTxn({ family_member_id: null }))

      render(<Transactions />)
      await waitFor(() => screen.getByDisplayValue('Jane'))

      fireEvent.change(screen.getByDisplayValue('Jane'), { target: { value: '' } })

      await waitFor(() => {
        expect(bankService.annotateTransaction).toHaveBeenCalledWith('txn-1', { family_member_id: null })
      })
    })
  })

  describe('CategoryPicker', () => {
    it('is not rendered on the All tab', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ is_hsa_eligible: true }),
      ])
      render(<Transactions />)
      await waitFor(() => screen.getByText('CVS Pharmacy'))
      expect(screen.queryByDisplayValue('— category —')).not.toBeInTheDocument()
    })

    it('is rendered on the HSA tab', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ is_hsa_eligible: true }),
      ])
      render(<Transactions />)
      await waitFor(() => screen.getByRole('button', { name: 'HSA Transactions' }))

      fireEvent.click(screen.getByRole('button', { name: 'HSA Transactions' }))

      await waitFor(() => {
        expect(screen.getByDisplayValue('— category —')).toBeInTheDocument()
      })
    })

    it('calls annotateTransaction with hsa_category when category is selected', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ is_hsa_eligible: true }),
      ])
      ;(bankService.annotateTransaction as any).mockResolvedValue(
        makeTxn({ is_hsa_eligible: true, hsa_category: 'dental' })
      )

      render(<Transactions />)
      await waitFor(() => screen.getByRole('button', { name: 'HSA Transactions' }))
      fireEvent.click(screen.getByRole('button', { name: 'HSA Transactions' }))

      await waitFor(() => screen.getByDisplayValue('— category —'))

      fireEvent.change(screen.getByDisplayValue('— category —'), { target: { value: 'dental' } })

      await waitFor(() => {
        expect(bankService.annotateTransaction).toHaveBeenCalledWith('txn-1', { hsa_category: 'dental' })
      })
    })
  })

  describe('client-side filters', () => {
    it('filters transactions by search term', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ id: 'txn-1', description: 'CVS Pharmacy' }),
        makeTxn({ id: 'txn-2', description: 'Spotify' }),
      ])
      render(<Transactions />)
      await waitFor(() => screen.getByText('Spotify'))

      const input = screen.getByPlaceholderText(/search description/i)
      fireEvent.change(input, { target: { value: 'cvs' } })

      expect(screen.getByText('CVS Pharmacy')).toBeInTheDocument()
      expect(screen.queryByText('Spotify')).not.toBeInTheDocument()
    })

    it('filters transactions by family member', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ id: 'txn-1', description: "Jane's Visit", family_member_id: 'member-1' }),
        makeTxn({ id: 'txn-2', description: 'Other Txn' }),
      ])
      ;(familyService.list as any).mockResolvedValue([mockMember])

      render(<Transactions />)
      await waitFor(() => screen.getByText('Other Txn'))

      // The filter bar "All people" select
      const memberFilter = screen.getAllByRole('combobox').find(
        el => (el as HTMLSelectElement).value === ''
          && el.querySelector
          && el.closest('[class*="flex"]')
      )
      // Use the combobox that has "All people" option
      const allPeopleSelect = screen.getByDisplayValue('All people')
      fireEvent.change(allPeopleSelect, { target: { value: 'member-1' } })

      expect(screen.getByText("Jane's Visit")).toBeInTheDocument()
      expect(screen.queryByText('Other Txn')).not.toBeInTheDocument()
    })

    it('filters transactions by start date', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ id: 'txn-1', description: 'Recent', transaction_date: '2026-03-15' }),
        makeTxn({ id: 'txn-2', description: 'Old', transaction_date: '2026-01-01' }),
      ])
      render(<Transactions />)
      await waitFor(() => screen.getByText('Old'))

      const dateInputs = screen.getAllByDisplayValue('')
      // First date input is start date
      const startDateInput = dateInputs.find(el => el.getAttribute('type') === 'date')!
      fireEvent.change(startDateInput, { target: { value: '2026-03-01' } })

      expect(screen.getByText('Recent')).toBeInTheDocument()
      expect(screen.queryByText('Old')).not.toBeInTheDocument()
    })

    it('shows Clear button when filters are active', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
      render(<Transactions />)
      await waitFor(() => screen.getByText('CVS Pharmacy'))

      expect(screen.queryByText('Clear')).not.toBeInTheDocument()

      const input = screen.getByPlaceholderText(/search description/i)
      fireEvent.change(input, { target: { value: 'cvs' } })

      expect(screen.getByText('Clear')).toBeInTheDocument()
    })

    it('clears all filters when Clear is clicked', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ id: 'txn-1', description: 'CVS Pharmacy' }),
        makeTxn({ id: 'txn-2', description: 'Spotify' }),
      ])
      render(<Transactions />)
      await waitFor(() => screen.getByText('Spotify'))

      const input = screen.getByPlaceholderText(/search description/i)
      fireEvent.change(input, { target: { value: 'cvs' } })
      expect(screen.queryByText('Spotify')).not.toBeInTheDocument()

      fireEvent.click(screen.getByText('Clear'))

      expect(screen.getByText('CVS Pharmacy')).toBeInTheDocument()
      expect(screen.getByText('Spotify')).toBeInTheDocument()
    })

    it('shows filtered count when filters are active', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ id: 'txn-1', description: 'CVS Pharmacy' }),
        makeTxn({ id: 'txn-2', description: 'Spotify' }),
      ])
      render(<Transactions />)
      await waitFor(() => screen.getByText('Spotify'))

      const input = screen.getByPlaceholderText(/search description/i)
      fireEvent.change(input, { target: { value: 'cvs' } })

      expect(screen.getByText(/filtered from 2/i)).toBeInTheDocument()
    })
  })
})
