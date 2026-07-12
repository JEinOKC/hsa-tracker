import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '../../test/utils'
import LmnPicker from '../LmnPicker'
import type { BankTransaction } from '../../services/bank'

vi.mock('../../services/lmn', () => ({
  lmnService: {
    listAll: vi.fn(),
  },
}))

vi.mock('../../services/bank', async () => {
  const actual = await vi.importActual('../../services/bank')
  return {
    ...actual,
    bankService: {
      annotateTransaction: vi.fn(),
    },
  }
})

import { lmnService } from '../../services/lmn'
import { bankService } from '../../services/bank'

const makeTxn = (overrides = {}): BankTransaction => ({
  id: 'txn-1',
  connection_id: 'conn-1',
  source: 'teller',
  provider: 'teller',
  provider_transaction_id: 'txn_abc',
  transaction_date: '2026-03-01',
  description: 'CVS Pharmacy',
  amount: '-42.00',
  transaction_type: 'card_payment',
  status: 'posted',
  details: null,
  created_at: '2026-03-01T00:00:00',
  is_hsa_eligible: true,
  family_member_id: 'member-1',
  hsa_category: null,
  eligible_amount: null,
  reimbursement_status: null,
  reimbursed_at: null,
  notes: null,
  account_name: null,
  institution_name: null,
  document_count: 0,
  lmn_document_id: null,
  auto_flag: null,
  rule_id: null,
  eligibility_warning: false,
  teller_category: null,
  ...overrides,
})

const makeLmn = (overrides = {}) => ({
  id: 'lmn-1',
  family_member_id: 'member-1',
  family_member_name: 'Test Member',
  original_filename: 'letter.pdf',
  content_type: 'application/pdf',
  file_size_bytes: 50000,
  label: 'Ortho LMN',
  provider_name: null,
  issue_date: null,
  expiration_date: null,
  notes: null,
  uploaded_at: '2026-03-01T00:00:00',
  url: 'https://s3.example.com/letter.pdf',
  ...overrides,
})

beforeEach(() => {
  vi.clearAllMocks()
})

describe('LmnPicker', () => {
  it('renders nothing when no LMNs exist', async () => {
    ;(lmnService.listAll as any).mockResolvedValue([])
    const { container } = render(<LmnPicker txn={makeTxn()} onChange={() => {}} />)
    await waitFor(() => {
      expect(container.querySelector('select')).not.toBeInTheDocument()
    })
  })

  it('renders dropdown with LMN options', async () => {
    ;(lmnService.listAll as any).mockResolvedValue([makeLmn()])
    render(<LmnPicker txn={makeTxn()} onChange={() => {}} />)
    await waitFor(() => {
      expect(screen.getByRole('combobox')).toBeInTheDocument()
    })
    expect(screen.getByText('None')).toBeInTheDocument()
    expect(screen.getByText(/Test Member: Ortho LMN/)).toBeInTheDocument()
  })

  it('calls annotateTransaction when selecting an LMN', async () => {
    ;(lmnService.listAll as any).mockResolvedValue([makeLmn()])
    const updatedTxn = makeTxn({ lmn_document_id: 'lmn-1' })
    ;(bankService.annotateTransaction as any).mockResolvedValue(updatedTxn)
    const onChange = vi.fn()

    render(<LmnPicker txn={makeTxn()} onChange={onChange} />)
    await waitFor(() => screen.getByRole('combobox'))

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'lmn-1' } })

    await waitFor(() => {
      expect(bankService.annotateTransaction).toHaveBeenCalledWith('txn-1', { lmn_document_id: 'lmn-1' })
      expect(onChange).toHaveBeenCalledWith(updatedTxn)
    })
  })

  it('clears LMN when selecting None', async () => {
    ;(lmnService.listAll as any).mockResolvedValue([makeLmn()])
    const updatedTxn = makeTxn({ lmn_document_id: null })
    ;(bankService.annotateTransaction as any).mockResolvedValue(updatedTxn)
    const onChange = vi.fn()

    render(<LmnPicker txn={makeTxn({ lmn_document_id: 'lmn-1' })} onChange={onChange} />)
    await waitFor(() => screen.getByRole('combobox'))

    fireEvent.change(screen.getByRole('combobox'), { target: { value: '' } })

    await waitFor(() => {
      expect(bankService.annotateTransaction).toHaveBeenCalledWith('txn-1', { lmn_document_id: null })
    })
  })
})
