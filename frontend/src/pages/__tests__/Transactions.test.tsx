import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '../../test/utils'
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

vi.mock('../../services/documents', () => ({
  documentService: {
    list: vi.fn(),
  },
}))

import { bankService } from '../../services/bank'
import { familyService } from '../../services/family'
import { documentService } from '../../services/documents'

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
  reimbursed_at: null,
  notes: null,
  account_name: 'HSA Checking',
  institution_name: 'First Bank',
  document_count: 0,
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
  ;(documentService.list as any).mockResolvedValue([])
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
        expect.objectContaining({ limit: 50 })
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
        expect(allTab.className).toContain('border-sky-600')
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

    it('does not show total header on All tab', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
      render(<Transactions />)
      await waitFor(() => screen.getByText('CVS Pharmacy'))
      expect(screen.queryByText('HSA total')).not.toBeInTheDocument()
      expect(screen.queryByText('Reimbursed total')).not.toBeInTheDocument()
    })

    it('shows Category column header on HSA tab but not All tab', async () => {
      render(<Transactions />)
      await waitFor(() => screen.getByRole('button', { name: 'HSA Transactions' }))

      expect(screen.queryByText('Category')).not.toBeInTheDocument()

      fireEvent.click(screen.getByRole('button', { name: 'HSA Transactions' }))

      await waitFor(() => {
        expect(screen.getByText('Category')).toBeInTheDocument()
      })
    })
  })

  describe('Reimbursed tab', () => {
    it('shows Reimbursed tab button', async () => {
      render(<Transactions />)
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Reimbursed' })).toBeInTheDocument()
      })
    })

    it('switches to Reimbursed tab and fetches with correct params', async () => {
      render(<Transactions />)
      await waitFor(() => screen.getByRole('button', { name: 'Reimbursed' }))

      fireEvent.click(screen.getByRole('button', { name: 'Reimbursed' }))

      await waitFor(() => {
        expect(bankService.listAllTransactions).toHaveBeenCalledWith(
          expect.objectContaining({ is_hsa_eligible: true, reimbursement_status: 'reimbursed' })
        )
      })
    })

    it('shows Reimbursed total header on Reimbursed tab', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ is_hsa_eligible: true, reimbursement_status: 'reimbursed', amount: '-50.00' }),
      ])
      render(<Transactions />)
      await waitFor(() => screen.getByRole('button', { name: 'Reimbursed' }))

      fireEvent.click(screen.getByRole('button', { name: 'Reimbursed' }))

      await waitFor(() => {
        expect(screen.getByText('Reimbursed total')).toBeInTheDocument()
      })
    })

    it('shows empty state for Reimbursed tab', async () => {
      render(<Transactions />)
      await waitFor(() => screen.getByRole('button', { name: 'Reimbursed' }))

      fireEvent.click(screen.getByRole('button', { name: 'Reimbursed' }))

      await waitFor(() => {
        expect(screen.getByText(/no reimbursed transactions yet/i)).toBeInTheDocument()
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

  describe('ReimburseToggle', () => {
    it('shows Reimburse button on HSA tab', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ is_hsa_eligible: true, reimbursement_status: null }),
      ])
      render(<Transactions />)
      await waitFor(() => screen.getByRole('button', { name: 'HSA Transactions' }))
      fireEvent.click(screen.getByRole('button', { name: 'HSA Transactions' }))

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Reimburse' })).toBeInTheDocument()
      })
    })

    it('shows Reimbursed badge when already reimbursed', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ is_hsa_eligible: true, reimbursement_status: 'reimbursed' }),
      ])
      render(<Transactions />)
      await waitFor(() => screen.getByRole('button', { name: 'HSA Transactions' }))
      fireEvent.click(screen.getByRole('button', { name: 'HSA Transactions' }))

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Reimbursed' })).toBeInTheDocument()
      })
    })

    it('calls annotateTransaction with reimbursed when Reimburse is clicked and date saved', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ is_hsa_eligible: true, reimbursement_status: null }),
      ])
      ;(bankService.annotateTransaction as any).mockResolvedValue(
        makeTxn({ is_hsa_eligible: true, reimbursement_status: 'reimbursed' })
      )
      render(<Transactions />)
      await waitFor(() => screen.getByRole('button', { name: 'HSA Transactions' }))
      fireEvent.click(screen.getByRole('button', { name: 'HSA Transactions' }))

      await waitFor(() => screen.getByRole('button', { name: 'Reimburse' }))
      fireEvent.click(screen.getByRole('button', { name: 'Reimburse' }))

      // Date picker appears — click Save to confirm
      await waitFor(() => screen.getByRole('button', { name: 'Save' }))
      fireEvent.click(screen.getByRole('button', { name: 'Save' }))

      await waitFor(() => {
        expect(bankService.annotateTransaction).toHaveBeenCalledWith('txn-1', {
          reimbursement_status: 'reimbursed',
          reimbursed_at: expect.any(String),
        })
      })
    })

    it('calls annotateTransaction with null reimbursement when Reimbursed badge is clicked (undo)', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ is_hsa_eligible: true, reimbursement_status: 'reimbursed' }),
      ])
      ;(bankService.annotateTransaction as any).mockResolvedValue(
        makeTxn({ is_hsa_eligible: true, reimbursement_status: null })
      )
      render(<Transactions />)
      await waitFor(() => screen.getByRole('button', { name: 'HSA Transactions' }))
      fireEvent.click(screen.getByRole('button', { name: 'HSA Transactions' }))

      // Two buttons named "Reimbursed" exist: the tab + the row toggle. Click the row toggle (last one).
      await waitFor(() => {
        const buttons = screen.getAllByRole('button', { name: 'Reimbursed' })
        expect(buttons.length).toBeGreaterThanOrEqual(2)
      })
      const allReimbursed = screen.getAllByRole('button', { name: 'Reimbursed' })
      const rowToggle = allReimbursed[allReimbursed.length - 1]
      fireEvent.click(rowToggle)

      await waitFor(() => {
        expect(bankService.annotateTransaction).toHaveBeenCalledWith('txn-1', {
          reimbursement_status: null,
          reimbursed_at: null,
        })
      })
    })
  })

  describe('ReimburseToggle date picker', () => {
    it('shows date input after clicking Reimburse', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ is_hsa_eligible: true, reimbursement_status: null }),
      ])
      render(<Transactions />)
      await waitFor(() => screen.getByRole('button', { name: 'HSA Transactions' }))
      fireEvent.click(screen.getByRole('button', { name: 'HSA Transactions' }))

      await waitFor(() => screen.getByRole('button', { name: 'Reimburse' }))
      fireEvent.click(screen.getByRole('button', { name: 'Reimburse' }))

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument()
      })
    })

    it('cancels date picker when ✕ is clicked', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ is_hsa_eligible: true, reimbursement_status: null }),
      ])
      render(<Transactions />)
      await waitFor(() => screen.getByRole('button', { name: 'HSA Transactions' }))
      fireEvent.click(screen.getByRole('button', { name: 'HSA Transactions' }))

      await waitFor(() => screen.getByRole('button', { name: 'Reimburse' }))
      fireEvent.click(screen.getByRole('button', { name: 'Reimburse' }))

      await waitFor(() => screen.getByRole('button', { name: 'Save' }))
      fireEvent.click(screen.getByRole('button', { name: '✕' }))

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Reimburse' })).toBeInTheDocument()
        expect(screen.queryByRole('button', { name: 'Save' })).not.toBeInTheDocument()
      })
    })
  })

  describe('receipt attachment badge', () => {
    it('shows amber badge for HSA transaction with no documents', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ is_hsa_eligible: true, document_count: 0 }),
      ])
      render(<Transactions />)
      await waitFor(() => {
        expect(screen.getByTitle('No receipt attached')).toBeInTheDocument()
      })
    })

    it('does not show amber badge for non-HSA transaction', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ is_hsa_eligible: false, document_count: 0 }),
      ])
      render(<Transactions />)
      await waitFor(() => screen.getByText('CVS Pharmacy'))
      expect(screen.queryByTitle('No receipt attached')).not.toBeInTheDocument()
    })

    it('does not show amber badge for HSA transaction that has documents', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ is_hsa_eligible: true, document_count: 1 }),
      ])
      render(<Transactions />)
      await waitFor(() => screen.getByText('CVS Pharmacy'))
      expect(screen.queryByTitle('No receipt attached')).not.toBeInTheDocument()
    })

    it('shows paperclip toggle button per row', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
      render(<Transactions />)
      await waitFor(() => {
        expect(screen.getByTitle('Attach receipts')).toBeInTheDocument()
      })
    })

    it('shows document count on paperclip when documents exist', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ document_count: 3 }),
      ])
      render(<Transactions />)
      await waitFor(() => {
        expect(screen.getByTitle('Attach receipts')).toHaveTextContent('3')
      })
    })

    it('expands DocumentUpload panel when paperclip is clicked', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
      render(<Transactions />)
      await waitFor(() => screen.getByTitle('Attach receipts'))

      fireEvent.click(screen.getByTitle('Attach receipts'))

      await waitFor(() => {
        expect(screen.getByText(/no receipts attached yet/i)).toBeInTheDocument()
      })
    })

    it('collapses DocumentUpload panel when paperclip is clicked again', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
      render(<Transactions />)
      await waitFor(() => screen.getByTitle('Attach receipts'))

      fireEvent.click(screen.getByTitle('Attach receipts'))
      await waitFor(() => screen.getByText(/no receipts attached yet/i))

      fireEvent.click(screen.getByTitle('Hide receipts'))

      await waitFor(() => {
        expect(screen.queryByText(/no receipts attached yet/i)).not.toBeInTheDocument()
      })
    })
  })

  describe('docs filter', () => {
    it('renders the docs filter dropdown', async () => {
      render(<Transactions />)
      await waitFor(() => {
        expect(screen.getByDisplayValue('Any docs')).toBeInTheDocument()
      })
    })

    it('sends has_documents=false when Missing receipts is selected', async () => {
      render(<Transactions />)
      await waitFor(() => screen.getByDisplayValue('Any docs'))

      fireEvent.change(screen.getByDisplayValue('Any docs'), { target: { value: 'missing' } })

      await waitFor(() => {
        expect(bankService.listAllTransactions).toHaveBeenCalledWith(
          expect.objectContaining({ has_documents: false })
        )
      })
    })

    it('sends has_documents=true when Has receipts is selected', async () => {
      render(<Transactions />)
      await waitFor(() => screen.getByDisplayValue('Any docs'))

      fireEvent.change(screen.getByDisplayValue('Any docs'), { target: { value: 'attached' } })

      await waitFor(() => {
        expect(bankService.listAllTransactions).toHaveBeenCalledWith(
          expect.objectContaining({ has_documents: true })
        )
      })
    })

    it('sends no has_documents param when Any docs is selected', async () => {
      render(<Transactions />)
      await waitFor(() => screen.getByDisplayValue('Any docs'))

      fireEvent.change(screen.getByDisplayValue('Any docs'), { target: { value: 'missing' } })
      await waitFor(() => screen.getByDisplayValue('Missing receipts'))

      fireEvent.change(screen.getByDisplayValue('Missing receipts'), { target: { value: '' } })

      await waitFor(() => {
        const calls = (bankService.listAllTransactions as any).mock.calls
        const lastCall = calls[calls.length - 1][0]
        expect(lastCall.has_documents).toBeUndefined()
      })
    })

    it('treats docs=missing URL param as an active filter', async () => {
      render(<Transactions />, { initialEntries: ['/?tab=hsa&docs=missing'] })
      await waitFor(() => {
        expect(bankService.listAllTransactions).toHaveBeenCalledWith(
          expect.objectContaining({ has_documents: false })
        )
      })
    })

    it('shows Clear button when docs filter is active', async () => {
      render(<Transactions />, { initialEntries: ['/?docs=missing'] })
      await waitFor(() => {
        expect(screen.getByText('Clear filters')).toBeInTheDocument()
      })
    })

    it('clears docs filter from URL when Clear is clicked', async () => {
      render(<Transactions />, { initialEntries: ['/?tab=hsa&docs=missing'] })
      await waitFor(() => screen.getByText('Clear filters'))

      fireEvent.click(screen.getByText('Clear filters'))

      await waitFor(() => {
        expect(bankService.listAllTransactions).toHaveBeenCalledWith(
          expect.objectContaining({ has_documents: undefined })
        )
      })
    })
  })

  describe('server-side filters', () => {
    it('sends search term to API after debounce', async () => {
      render(<Transactions />)
      await waitFor(() => screen.getByPlaceholderText(/search description/i))

      const input = screen.getByPlaceholderText(/search description/i)
      fireEvent.change(input, { target: { value: 'cvs' } })

      await waitFor(() => {
        const calls = (bankService.listAllTransactions as any).mock.calls
        expect(calls.some((c: any[]) => c[0]?.search === 'cvs')).toBe(true)
      })
    })

    it('sends family_member_id to API when member filter changes', async () => {
      ;(familyService.list as any).mockResolvedValue([mockMember])
      render(<Transactions />)
      await waitFor(() => screen.getByDisplayValue('All people'))

      fireEvent.change(screen.getByDisplayValue('All people'), { target: { value: 'member-1' } })

      await waitFor(() => {
        expect(bankService.listAllTransactions).toHaveBeenCalledWith(
          expect.objectContaining({ family_member_id: 'member-1' })
        )
      })
    })

    it('sends start_date to API when date filter changes', async () => {
      render(<Transactions />)
      await waitFor(() => screen.getAllByDisplayValue(''))

      const dateInput = screen.getAllByDisplayValue('').find(
        el => el.getAttribute('type') === 'date'
      )!
      fireEvent.change(dateInput, { target: { value: '2026-03-01' } })

      await waitFor(() => {
        expect(bankService.listAllTransactions).toHaveBeenCalledWith(
          expect.objectContaining({ start_date: '2026-03-01' })
        )
      })
    })

    it('shows Clear button when filters are active', async () => {
      render(<Transactions />)
      await waitFor(() => screen.getByPlaceholderText(/search description/i))

      expect(screen.queryByText('Clear filters')).not.toBeInTheDocument()

      fireEvent.change(screen.getByPlaceholderText(/search description/i), { target: { value: 'cvs' } })

      expect(screen.getByText('Clear filters')).toBeInTheDocument()
    })

    it('resets filters and reloads when Clear is clicked', async () => {
      render(<Transactions />)
      await waitFor(() => screen.getByPlaceholderText(/search description/i))

      fireEvent.change(screen.getByPlaceholderText(/search description/i), { target: { value: 'cvs' } })
      await waitFor(() => screen.getByText('Clear filters'))

      fireEvent.click(screen.getByText('Clear filters'))

      expect((screen.getByPlaceholderText(/search description/i) as HTMLInputElement).value).toBe('')
    })
  })
})
