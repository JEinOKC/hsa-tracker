import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '../../test/utils'
import Transactions from '../Transactions'

vi.mock('../../services/bank', () => ({
  bankService: {
    listAllTransactions: vi.fn(),
    annotateTransaction: vi.fn(),
    listTransactionCategories: vi.fn(),
    countTransactions: vi.fn(),
    getSmartFilterStatus: vi.fn(),
    setCategoryOverride: vi.fn(),
    deleteCategoryOverride: vi.fn(),
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

vi.mock('../../services/rules', () => ({
  rulesService: {
    create: vi.fn(),
    applyAll: vi.fn(),
    preview: vi.fn(),
  },
}))

vi.mock('../../services/household', () => ({
  householdService: {
    getMine: vi.fn(),
  },
}))

vi.mock('../../services/receipts', () => ({
  receiptsService: {
    listTransactionFills: vi.fn(),
    listLineItems: vi.fn(),
    importLineItemsCsv: vi.fn(),
    createLineItem: vi.fn(),
    updateLineItem: vi.fn(),
    deleteLineItem: vi.fn(),
    unlinkFill: vi.fn(),
  },
}))

import { bankService } from '../../services/bank'
import { familyService } from '../../services/family'
import { documentService } from '../../services/documents'
import { rulesService } from '../../services/rules'
import { householdService } from '../../services/household'
import { receiptsService } from '../../services/receipts'

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
  auto_flag: null,
  rule_id: null,
  eligibility_warning: false,
  teller_category: null,
  eligible_amount: null,
  ...overrides,
})

const mockMember = {
  id: 'member-1',
  user_id: 'user-1',
  name: 'Jane',
  member_relationship: 'spouse',
  date_of_birth: null,
}

const mockHousehold = {
  id: 'hh-1',
  name: 'Test Household',
  created_by_id: 'user-1',
  strict_eligibility: false,
  is_admin: true,
}

beforeEach(() => {
  vi.clearAllMocks()
  ;(bankService.listAllTransactions as any).mockResolvedValue([])
  ;(bankService.listTransactionCategories as any).mockResolvedValue([])
  ;(bankService.countTransactions as any).mockResolvedValue(0)
  ;(bankService.getSmartFilterStatus as any).mockResolvedValue([])
  ;(familyService.list as any).mockResolvedValue([])
  ;(documentService.list as any).mockResolvedValue([])
  ;(householdService.getMine as any).mockResolvedValue(mockHousehold)
  ;(receiptsService.listTransactionFills as any).mockResolvedValue([])
  ;(receiptsService.listLineItems as any).mockResolvedValue([])
  ;(rulesService.applyAll as any).mockResolvedValue({ updated: 0 })
  ;(rulesService.create as any).mockResolvedValue({
    id: 'rule-1', name: 'Hide: CVS Pharmacy', priority: 0, is_active: true,
    conditions: [], actions: [], user_id: 'u1', created_at: '', updated_at: '',
  })
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
    ;(bankService.countTransactions as any).mockResolvedValue(2)
    render(<Transactions />)
    await waitFor(() => {
      expect(screen.getByText(/showing 2 of 2 transactions/i)).toBeInTheDocument()
    })
  })

  describe('category filter', () => {
    it('shows warning banner when teller category filter is active', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
      ;(bankService.listTransactionCategories as any).mockResolvedValue(['health'])
      ;(bankService.countTransactions as any).mockResolvedValue(1)
      render(<Transactions />)
      await waitFor(() => screen.getByText('CVS Pharmacy'))

      fireEvent.change(screen.getByDisplayValue('Smart'), { target: { value: 'health' } })

      await waitFor(() => {
        expect(screen.getByText(/older transactions may not have bank-provided category data/i)).toBeInTheDocument()
      })
    })

    it('does not show category warning when no category filter is active', async () => {
      render(<Transactions />)
      await waitFor(() => expect(bankService.listAllTransactions).toHaveBeenCalled())
      expect(screen.queryByText(/older transactions may not have bank-provided category data/i)).not.toBeInTheDocument()
    })

    it('shows Smart mode hidden status when category is smart-hidden', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
      ;(bankService.listTransactionCategories as any).mockResolvedValue(['dining'])
      ;(bankService.countTransactions as any).mockResolvedValue(1)
      ;(bankService.getSmartFilterStatus as any).mockResolvedValue([{
        category: 'dining', is_hidden_by_default: true, is_auto_promoted: false,
        pin_mode: null, effective_smart_hidden: true, reviewed_count: 0, hsa_rate: 0,
      }])
      render(<Transactions />)
      await waitFor(() => screen.getByText('CVS Pharmacy'))
      fireEvent.change(screen.getByDisplayValue('Smart'), { target: { value: 'dining' } })
      await waitFor(() => {
        expect(screen.getByText(/always show in smart mode/i)).toBeInTheDocument()
        expect(screen.getAllByText(/smart mode/i).length).toBeGreaterThan(0)
      })
    })

    it('shows auto-promoted label when category has high HSA rate', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
      ;(bankService.listTransactionCategories as any).mockResolvedValue(['shopping'])
      ;(bankService.countTransactions as any).mockResolvedValue(1)
      ;(bankService.getSmartFilterStatus as any).mockResolvedValue([{
        category: 'shopping', is_hidden_by_default: true, is_auto_promoted: true,
        pin_mode: null, effective_smart_hidden: false, reviewed_count: 12, hsa_rate: 0.25,
      }])
      render(<Transactions />)
      await waitFor(() => screen.getByText('CVS Pharmacy'))
      fireEvent.change(screen.getByDisplayValue('Smart'), { target: { value: 'shopping' } })
      await waitFor(() => {
        expect(screen.getByText(/auto-promoted/i)).toBeInTheDocument()
        expect(screen.getByText(/25%/i)).toBeInTheDocument()
      })
    })

    it('shows remove pin button when category has a pin', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
      ;(bankService.listTransactionCategories as any).mockResolvedValue(['dining'])
      ;(bankService.countTransactions as any).mockResolvedValue(1)
      ;(bankService.getSmartFilterStatus as any).mockResolvedValue([{
        category: 'dining', is_hidden_by_default: true, is_auto_promoted: false,
        pin_mode: 'show', effective_smart_hidden: false, reviewed_count: 0, hsa_rate: 0,
      }])
      render(<Transactions />)
      await waitFor(() => screen.getByText('CVS Pharmacy'))
      fireEvent.change(screen.getByDisplayValue('Smart'), { target: { value: 'dining' } })
      await waitFor(() => {
        expect(screen.getByText(/remove pin/i)).toBeInTheDocument()
      })
    })

    it('calls setCategoryOverride when pinning a category', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
      ;(bankService.listTransactionCategories as any).mockResolvedValue(['dining'])
      ;(bankService.countTransactions as any).mockResolvedValue(1)
      ;(bankService.getSmartFilterStatus as any).mockResolvedValue([{
        category: 'dining', is_hidden_by_default: true, is_auto_promoted: false,
        pin_mode: null, effective_smart_hidden: true, reviewed_count: 0, hsa_rate: 0,
      }])
      ;(bankService.setCategoryOverride as any).mockResolvedValue({ category: 'dining', pin_mode: 'show' })
      render(<Transactions />)
      await waitFor(() => screen.getByText('CVS Pharmacy'))
      fireEvent.change(screen.getByDisplayValue('Smart'), { target: { value: 'dining' } })
      await waitFor(() => screen.getByText(/always show in smart mode/i))
      fireEvent.click(screen.getByText(/always show in smart mode/i))
      await waitFor(() => {
        expect(bankService.setCategoryOverride).toHaveBeenCalledWith('dining', 'show')
      })
    })

    it('calls deleteCategoryOverride when removing a pin', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
      ;(bankService.listTransactionCategories as any).mockResolvedValue(['dining'])
      ;(bankService.countTransactions as any).mockResolvedValue(1)
      ;(bankService.getSmartFilterStatus as any).mockResolvedValue([{
        category: 'dining', is_hidden_by_default: true, is_auto_promoted: false,
        pin_mode: 'show', effective_smart_hidden: false, reviewed_count: 0, hsa_rate: 0,
      }])
      ;(bankService.deleteCategoryOverride as any).mockResolvedValue(undefined)
      render(<Transactions />)
      await waitFor(() => screen.getByText('CVS Pharmacy'))
      fireEvent.change(screen.getByDisplayValue('Smart'), { target: { value: 'dining' } })
      await waitFor(() => screen.getByText(/remove pin/i))
      fireEvent.click(screen.getByText(/remove pin/i))
      await waitFor(() => {
        expect(bankService.deleteCategoryOverride).toHaveBeenCalledWith('dining')
      })
    })

    it('shows Showing X of Y when count exceeds loaded transactions', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
      ;(bankService.countTransactions as any).mockResolvedValue(42)
      render(<Transactions />)
      await waitFor(() => {
        expect(screen.getByText(/showing 1 of 42 transactions/i)).toBeInTheDocument()
      })
    })

    it('sends include_potential_hsa=true when on HSA tab', async () => {
      render(<Transactions />)
      await waitFor(() => screen.getByRole('button', { name: 'HSA Transactions' }))
      fireEvent.click(screen.getByRole('button', { name: 'HSA Transactions' }))
      await waitFor(() => {
        expect(bankService.listAllTransactions).toHaveBeenCalledWith(
          expect.objectContaining({ is_hsa_eligible: true, include_potential_hsa: true })
        )
      })
    })
  })

  describe('potential HSA callout', () => {
    it('shows callout on HSA tab when potential_hsa rows are present', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ is_hsa_eligible: null, auto_flag: 'potential_hsa' }),
      ])
      ;(bankService.countTransactions as any).mockResolvedValue(1)
      render(<Transactions />)
      await waitFor(() => screen.getByRole('button', { name: 'HSA Transactions' }))
      fireEvent.click(screen.getByRole('button', { name: 'HSA Transactions' }))
      await waitFor(() => {
        expect(screen.getByText(/need your review/i)).toBeInTheDocument()
      })
    })

    it('does not show callout on All tab even with potential_hsa rows', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ is_hsa_eligible: null, auto_flag: 'potential_hsa' }),
      ])
      render(<Transactions />)
      await waitFor(() => screen.getByText('CVS Pharmacy'))
      expect(screen.queryByText(/need your review/i)).not.toBeInTheDocument()
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

  describe('HsaStatusBadge', () => {
    it('shows HSA badge (read-only) for eligible transaction', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn({ is_hsa_eligible: true })])
      render(<Transactions />)
      await waitFor(() => {
        expect(screen.getByTestId('hsa-badge')).toBeInTheDocument()
      })
    })

    it('shows Not HSA badge (read-only) for ineligible transaction', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn({ is_hsa_eligible: false })])
      render(<Transactions />)
      await waitFor(() => {
        expect(screen.getByTestId('not-hsa-badge')).toBeInTheDocument()
      })
    })

    it('shows no HSA badge for unreviewed transaction', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn({ is_hsa_eligible: null })])
      render(<Transactions />)
      await waitFor(() => screen.getByText('CVS Pharmacy'))
      expect(screen.queryByTestId('hsa-badge')).not.toBeInTheDocument()
      expect(screen.queryByTestId('not-hsa-badge')).not.toBeInTheDocument()
    })
  })

  describe('TagDialog', () => {
    it('clicking Tag opens the dialog with all options', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
      render(<Transactions />)
      await waitFor(() => screen.getByTitle('Tag this transaction'))
      fireEvent.click(screen.getByTitle('Tag this transaction'))
      await waitFor(() => {
        expect(screen.getByText('Tag transaction')).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /mark as hsa eligible/i })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /mark as not hsa/i })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /create hsa rule/i })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /hide this transaction/i })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /create hide rule/i })).toBeInTheDocument()
      })
    })

    it('"Mark as HSA eligible" calls annotateTransaction with true and updates row', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn({ is_hsa_eligible: null })])
      ;(bankService.annotateTransaction as any).mockResolvedValue(makeTxn({ is_hsa_eligible: true }))

      render(<Transactions />)
      await waitFor(() => screen.getByTitle('Tag this transaction'))
      fireEvent.click(screen.getByTitle('Tag this transaction'))
      await waitFor(() => screen.getByRole('button', { name: /mark as hsa eligible/i }))
      fireEvent.click(screen.getByRole('button', { name: /mark as hsa eligible/i }))

      await waitFor(() => {
        expect(bankService.annotateTransaction).toHaveBeenCalledWith('txn-1', { is_hsa_eligible: true })
        expect(screen.queryByText('Tag transaction')).not.toBeInTheDocument()
      })
      expect(bankService.listAllTransactions).toHaveBeenCalledTimes(1)
    })

    it('"Mark as Not HSA" calls annotateTransaction with false', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn({ is_hsa_eligible: null })])
      ;(bankService.annotateTransaction as any).mockResolvedValue(makeTxn({ is_hsa_eligible: false }))

      render(<Transactions />)
      await waitFor(() => screen.getByTitle('Tag this transaction'))
      fireEvent.click(screen.getByTitle('Tag this transaction'))
      await waitFor(() => screen.getByRole('button', { name: /mark as not hsa/i }))
      fireEvent.click(screen.getByRole('button', { name: /mark as not hsa/i }))

      await waitFor(() => {
        expect(bankService.annotateTransaction).toHaveBeenCalledWith('txn-1', { is_hsa_eligible: false })
      })
    })

    it('"Create HSA rule" opens RuleEditor pre-filled with mark_hsa action', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
      render(<Transactions />)
      await waitFor(() => screen.getByTitle('Tag this transaction'))
      fireEvent.click(screen.getByTitle('Tag this transaction'))
      await waitFor(() => screen.getByRole('button', { name: /create hsa rule/i }))
      fireEvent.click(screen.getByRole('button', { name: /create hsa rule/i }))
      await waitFor(() => {
        expect(screen.getByDisplayValue('HSA: CVS Pharmacy')).toBeInTheDocument()
        expect(screen.getByDisplayValue('CVS Pharmacy')).toBeInTheDocument()
      })
    })

    it('"Hide this transaction" hides it and removes from list', async () => {
      ;(bankService.listAllTransactions as any)
        .mockResolvedValueOnce([makeTxn()])  // initial load
        .mockResolvedValue([])               // reload after hiding (hidden txns excluded)
      ;(bankService.annotateTransaction as any).mockResolvedValue(makeTxn({ auto_flag: 'hidden' }))
      render(<Transactions />)
      await waitFor(() => screen.getByTitle('Tag this transaction'))
      fireEvent.click(screen.getByTitle('Tag this transaction'))
      await waitFor(() => screen.getByRole('button', { name: /hide this transaction/i }))
      fireEvent.click(screen.getByRole('button', { name: /hide this transaction/i }))
      await waitFor(() => {
        expect(bankService.annotateTransaction).toHaveBeenCalledWith('txn-1', { auto_flag: 'hidden' })
        expect(screen.queryByText('CVS Pharmacy')).not.toBeInTheDocument()
      })
    })

    it('"Create hide rule" opens RuleEditor pre-filled with hide action', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
      render(<Transactions />)
      await waitFor(() => screen.getByTitle('Tag this transaction'))
      fireEvent.click(screen.getByTitle('Tag this transaction'))
      await waitFor(() => screen.getByRole('button', { name: /create hide rule/i }))
      fireEvent.click(screen.getByRole('button', { name: /create hide rule/i }))
      await waitFor(() => {
        expect(screen.getByDisplayValue('Hide: CVS Pharmacy')).toBeInTheDocument()
        expect(screen.getByDisplayValue('CVS Pharmacy')).toBeInTheDocument()
      })
    })

    it('Cancel button closes the dialog', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
      render(<Transactions />)
      await waitFor(() => screen.getByTitle('Tag this transaction'))
      fireEvent.click(screen.getByTitle('Tag this transaction'))
      await waitFor(() => screen.getByText('Tag transaction'))
      fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
      await waitFor(() => {
        expect(screen.queryByText('Tag transaction')).not.toBeInTheDocument()
      })
    })

    it('does not show Tag button when transaction is already hidden', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn({ auto_flag: 'hidden' })])
      render(<Transactions />)
      await waitFor(() => screen.getByText('CVS Pharmacy'))
      expect(screen.queryByTitle('Tag this transaction')).not.toBeInTheDocument()
    })

    it('after rule save shows success toast mentioning Settings → Rules', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
      ;(rulesService.create as any).mockResolvedValue({
        id: 'rule-1', name: 'Hide: CVS Pharmacy', priority: 0, is_active: true,
        conditions: [], actions: [], user_id: 'u1', created_at: '', updated_at: '',
      })
      ;(rulesService.applyAll as any).mockResolvedValue({ updated: 3 })
      render(<Transactions />)
      await waitFor(() => screen.getByTitle('Tag this transaction'))
      fireEvent.click(screen.getByTitle('Tag this transaction'))
      await waitFor(() => screen.getByRole('button', { name: /create hide rule/i }))
      fireEvent.click(screen.getByRole('button', { name: /create hide rule/i }))
      await waitFor(() => screen.getByRole('button', { name: 'Save Rule' }))
      fireEvent.click(screen.getByRole('button', { name: 'Save Rule' }))
      await waitFor(() => {
        expect(screen.getByText(/Settings → Rules/)).toBeInTheDocument()
      })
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

    it('expands annotation controls when the transaction row itself is clicked', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
      ;(familyService.list as any).mockResolvedValue([mockMember])
      render(<Transactions />)
      await waitFor(() => screen.getByText('CVS Pharmacy'))

      // Before expanding, mobile annotation controls are not visible
      expect(screen.queryByText(/no receipts attached yet/i)).not.toBeInTheDocument()

      // Click the row div itself (not the paperclip)
      fireEvent.click(screen.getByText('CVS Pharmacy'))

      await waitFor(() => {
        expect(screen.getByText(/no receipts attached yet/i)).toBeInTheDocument()
      })
    })

    it('shows mobile annotation controls (HSA toggle + person picker) in expanded section', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([makeTxn()])
      ;(familyService.list as any).mockResolvedValue([mockMember])
      render(<Transactions />)
      await waitFor(() => screen.getByText('CVS Pharmacy'))

      fireEvent.click(screen.getByText('CVS Pharmacy'))

      await waitFor(() => {
        // Tag button and MemberPicker both render in the mobile expandable section
        const tagButtons = screen.getAllByRole('button', { name: 'Tag' })
        expect(tagButtons.length).toBeGreaterThan(0)
        const personPickers = screen.getAllByDisplayValue('— person —')
        expect(personPickers.length).toBeGreaterThan(0)
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

  describe('Potential HSA badge', () => {
    it('shows Potential HSA badge when auto_flag is potential_hsa and is_hsa_eligible is null', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ auto_flag: 'potential_hsa', is_hsa_eligible: null }),
      ])
      render(<Transactions />)
      await waitFor(() => {
        expect(screen.getByTitle('Potential HSA expense')).toBeInTheDocument()
        expect(screen.getByText('Potential HSA')).toBeInTheDocument()
      })
    })

    it('does not show Potential HSA badge when is_hsa_eligible is true', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ auto_flag: 'potential_hsa', is_hsa_eligible: true }),
      ])
      render(<Transactions />)
      await waitFor(() => screen.getByText('CVS Pharmacy'))
      expect(screen.queryByTitle('Potential HSA expense')).not.toBeInTheDocument()
    })

    it('does not show Potential HSA badge when auto_flag is null', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ auto_flag: null, is_hsa_eligible: null }),
      ])
      render(<Transactions />)
      await waitFor(() => screen.getByText('CVS Pharmacy'))
      expect(screen.queryByTitle('Potential HSA expense')).not.toBeInTheDocument()
    })

    it('does not show Potential HSA badge when auto_flag is hidden', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ auto_flag: 'hidden', is_hsa_eligible: null }),
      ])
      render(<Transactions />)
      await waitFor(() => screen.getByText('CVS Pharmacy'))
      expect(screen.queryByTitle('Potential HSA expense')).not.toBeInTheDocument()
    })
  })

  describe('show hidden filter', () => {
    it('renders the Show hidden checkbox', async () => {
      render(<Transactions />)
      await waitFor(() => {
        expect(screen.getByLabelText(/show hidden/i)).toBeInTheDocument()
      })
    })

    it('sends show_hidden=true when checkbox is checked', async () => {
      render(<Transactions />)
      await waitFor(() => screen.getByLabelText(/show hidden/i))

      fireEvent.click(screen.getByLabelText(/show hidden/i))

      await waitFor(() => {
        expect(bankService.listAllTransactions).toHaveBeenCalledWith(
          expect.objectContaining({ show_hidden: true })
        )
      })
    })

    it('does not send show_hidden when unchecked', async () => {
      render(<Transactions />)
      await waitFor(() => {
        expect(bankService.listAllTransactions).toHaveBeenCalledWith(
          expect.objectContaining({ show_hidden: undefined })
        )
      })
    })

    it('shows Clear filters when show_hidden is checked', async () => {
      render(<Transactions />)
      await waitFor(() => screen.getByLabelText(/show hidden/i))

      fireEvent.click(screen.getByLabelText(/show hidden/i))

      await waitFor(() => {
        expect(screen.getByText('Clear filters')).toBeInTheDocument()
      })
    })
  })


  describe('eligibility warning badge', () => {
    it('shows warning badge when eligibility_warning is true and member is assigned', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ family_member_id: 'member-1', eligibility_warning: true }),
      ])
      ;(familyService.list as any).mockResolvedValue([mockMember])
      render(<Transactions />)
      await waitFor(() => {
        expect(screen.getByTitle(/outside.*coverage window/i)).toBeInTheDocument()
      })
    })

    it('does not show warning badge when eligibility_warning is false', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ family_member_id: 'member-1', eligibility_warning: false }),
      ])
      ;(familyService.list as any).mockResolvedValue([mockMember])
      render(<Transactions />)
      await waitFor(() => screen.getByText('CVS Pharmacy'))
      expect(screen.queryByTitle(/outside.*coverage window/i)).not.toBeInTheDocument()
    })

    it('does not show warning badge when eligibility_warning is true but no member assigned', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ family_member_id: null, eligibility_warning: true }),
      ])
      render(<Transactions />)
      await waitFor(() => screen.getByText('CVS Pharmacy'))
      expect(screen.queryByTitle(/outside.*coverage window/i)).not.toBeInTheDocument()
    })
  })

  describe('strict tab total', () => {
    it('excludes warned transactions from HSA total when strict_eligibility is true', async () => {
      ;(householdService.getMine as any).mockResolvedValue({ ...mockHousehold, strict_eligibility: true })
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ id: 'txn-1', is_hsa_eligible: true, amount: '-100.00', eligibility_warning: false }),
        makeTxn({ id: 'txn-2', is_hsa_eligible: true, amount: '-50.00', eligibility_warning: true }),
      ])
      render(<Transactions />)
      await waitFor(() => screen.getByRole('button', { name: 'HSA Transactions' }))
      fireEvent.click(screen.getByRole('button', { name: 'HSA Transactions' }))
      await waitFor(() => {
        // Only the non-warned transaction (-100.00) should count
        expect(screen.getByText('-$100.00')).toBeInTheDocument()
      })
    })

    it('includes all transactions in HSA total when strict_eligibility is false', async () => {
      ;(householdService.getMine as any).mockResolvedValue({ ...mockHousehold, strict_eligibility: false })
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ id: 'txn-1', is_hsa_eligible: true, amount: '-100.00', eligibility_warning: false }),
        makeTxn({ id: 'txn-2', is_hsa_eligible: true, amount: '-50.00', eligibility_warning: true }),
      ])
      render(<Transactions />)
      await waitFor(() => screen.getByRole('button', { name: 'HSA Transactions' }))
      fireEvent.click(screen.getByRole('button', { name: 'HSA Transactions' }))
      await waitFor(() => {
        // Both transactions (-150.00) should count
        expect(screen.getByText('-$150.00')).toBeInTheDocument()
      })
    })

    it('shows strict label suffix on HSA total when strict_eligibility is true', async () => {
      ;(householdService.getMine as any).mockResolvedValue({ ...mockHousehold, strict_eligibility: true })
      ;(bankService.listAllTransactions as any).mockResolvedValue([
        makeTxn({ id: 'txn-1', is_hsa_eligible: true, amount: '-75.00' }),
      ])
      render(<Transactions />)
      await waitFor(() => screen.getByRole('button', { name: 'HSA Transactions' }))
      fireEvent.click(screen.getByRole('button', { name: 'HSA Transactions' }))
      await waitFor(() => {
        expect(screen.getByText(/strict/i)).toBeInTheDocument()
      })
    })
  })

  describe('Potential HSA only filter', () => {
    it('renders the All flags dropdown', async () => {
      render(<Transactions />)
      await waitFor(() => {
        expect(screen.getByDisplayValue('All flags')).toBeInTheDocument()
      })
    })

    it('sends auto_flag=potential_hsa when Potential HSA only is selected', async () => {
      render(<Transactions />)
      await waitFor(() => screen.getByDisplayValue('All flags'))

      fireEvent.change(screen.getByDisplayValue('All flags'), {
        target: { value: 'potential_hsa' },
      })

      await waitFor(() => {
        expect(bankService.listAllTransactions).toHaveBeenCalledWith(
          expect.objectContaining({ auto_flag: 'potential_hsa' })
        )
      })
    })

    it('does not send auto_flag when All flags is selected', async () => {
      render(<Transactions />)
      await waitFor(() => screen.getByDisplayValue('All flags'))

      fireEvent.change(screen.getByDisplayValue('All flags'), {
        target: { value: 'potential_hsa' },
      })
      await waitFor(() => screen.getByDisplayValue('Potential HSA only'))

      fireEvent.change(screen.getByDisplayValue('Potential HSA only'), {
        target: { value: '' },
      })

      await waitFor(() => {
        const calls = (bankService.listAllTransactions as any).mock.calls
        const lastCall = calls[calls.length - 1][0]
        expect(lastCall.auto_flag).toBeUndefined()
      })
    })
  })

  describe('TagDialog merchant memory', () => {
    const txnWithMerchant = makeTxn({
      description: 'NASHBIRD CHICKEN',
      details: { counterparty: { name: 'NASHBIRD CHICKEN' } },
    })
    const txnNoMerchant = makeTxn({
      description: null,
      details: null,
    })

    beforeEach(() => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([txnWithMerchant])
      ;(bankService.countTransactions as any).mockResolvedValue(1)
      ;(bankService.annotateTransaction as any).mockResolvedValue({
        ...txnWithMerchant,
        is_hsa_eligible: false,
      })
    })

    it('shows merchant memory prompt after marking Not HSA when merchant is known', async () => {
      render(<Transactions />)
      await waitFor(() => screen.getByText('NASHBIRD CHICKEN'))

      fireEvent.click(screen.getByTitle('Tag this transaction'))
      await waitFor(() => screen.getByText('Mark as Not HSA'))

      fireEvent.click(screen.getByText('Mark as Not HSA'))
      await waitFor(() => {
        expect(screen.getByText(/want to hide all/i)).toBeInTheDocument()
        expect(screen.getByText('Yes, hide all')).toBeInTheDocument()
      })
    })

    it('creates hide rule when user confirms merchant hide', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([txnWithMerchant])
      render(<Transactions />)
      await waitFor(() => screen.getByText('NASHBIRD CHICKEN'))

      fireEvent.click(screen.getByTitle('Tag this transaction'))
      await waitFor(() => screen.getByText('Mark as Not HSA'))
      fireEvent.click(screen.getByText('Mark as Not HSA'))

      await waitFor(() => screen.getByText('Yes, hide all'))
      fireEvent.click(screen.getByText('Yes, hide all'))

      await waitFor(() => {
        expect(rulesService.create).toHaveBeenCalledWith(
          expect.objectContaining({
            actions: [{ action_type: 'hide' }],
            conditions: [expect.objectContaining({ value: 'NASHBIRD CHICKEN' })],
          })
        )
        expect(rulesService.applyAll).toHaveBeenCalled()
      })
    })

    it('does not create rule when user clicks No thanks', async () => {
      render(<Transactions />)
      await waitFor(() => screen.getByText('NASHBIRD CHICKEN'))

      fireEvent.click(screen.getByTitle('Tag this transaction'))
      await waitFor(() => screen.getByText('Mark as Not HSA'))
      fireEvent.click(screen.getByText('Mark as Not HSA'))

      await waitFor(() => screen.getByText('No thanks'))
      fireEvent.click(screen.getByText('No thanks'))

      expect(rulesService.create).not.toHaveBeenCalled()
    })

    it('closes dialog immediately after marking Not HSA when no merchant name', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([txnNoMerchant])
      ;(bankService.annotateTransaction as any).mockResolvedValue({
        ...txnNoMerchant,
        is_hsa_eligible: false,
      })
      render(<Transactions />)
      await waitFor(() => expect(bankService.listAllTransactions).toHaveBeenCalled())

      fireEvent.click(screen.getByTitle('Tag this transaction'))
      await waitFor(() => screen.getByText('Mark as Not HSA'))
      fireEvent.click(screen.getByText('Mark as Not HSA'))

      await waitFor(() => {
        expect(screen.queryByText(/want to hide all/i)).not.toBeInTheDocument()
        expect(screen.queryByText('Tag transaction')).not.toBeInTheDocument()
      })
    })

    it('shows flag prompt after marking as HSA when merchant is known', async () => {
      ;(bankService.listAllTransactions as any).mockResolvedValue([txnWithMerchant])
      ;(bankService.annotateTransaction as any).mockResolvedValue({
        ...txnWithMerchant,
        is_hsa_eligible: true,
      })
      render(<Transactions />)
      await waitFor(() => screen.getByText('NASHBIRD CHICKEN'))

      fireEvent.click(screen.getByTitle('Tag this transaction'))
      await waitFor(() => screen.getByText('Mark as HSA eligible'))
      fireEvent.click(screen.getByText('Mark as HSA eligible'))

      await waitFor(() => {
        expect(screen.getByText(/flag future/i)).toBeInTheDocument()
        expect(screen.getByText('Yes, flag them')).toBeInTheDocument()
      })
    })
  })
})
