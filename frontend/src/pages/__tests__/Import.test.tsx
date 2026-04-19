import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '../../test/utils'
import Import from '../Import'

vi.mock('../../services/receipts', () => ({
  receiptsService: {
    importCvsPharmacy: vi.fn(),
    listPharmacyFills: vi.fn(),
    listTransactionFills: vi.fn(),
    listLineItems: vi.fn(),
    linkFill: vi.fn(),
    unlinkFill: vi.fn(),
    importLineItemsCsv: vi.fn(),
    createLineItem: vi.fn(),
    updateLineItem: vi.fn(),
    deleteLineItem: vi.fn(),
    downloadLineItemsTemplate: vi.fn(),
  },
}))

import { receiptsService } from '../../services/receipts'

const makeResult = (overrides = {}) => ({
  batch_id: 'batch-1',
  row_count: 2,
  matched: 2,
  unmatched: 0,
  fills: [
    {
      id: 'fill-1',
      drug_name: 'WIXELA 250-50 INHUB',
      rx_number: '1351781',
      fill_date: '2026-03-27',
      amount_paid: '10.00',
      pharmacy: 'CVS Pharmacy',
      member_name: 'JAMES',
      transaction_id: 'txn-1',
      matched: true,
    },
    {
      id: 'fill-2',
      drug_name: 'LISINOPRIL 10MG',
      rx_number: '9999999',
      fill_date: '2026-03-15',
      amount_paid: '10.00',
      pharmacy: 'CVS Pharmacy',
      member_name: 'JAMES',
      transaction_id: null,
      matched: false,
    },
  ],
  ...overrides,
})

beforeEach(() => {
  vi.clearAllMocks()
})

describe('Import page', () => {
  it('renders the page title', () => {
    render(<Import />)
    expect(screen.getByText('Import')).toBeInTheDocument()
  })

  it('renders the CVS pharmacy section', () => {
    render(<Import />)
    expect(screen.getByText('CVS Pharmacy')).toBeInTheDocument()
  })

  it('renders the upload button', () => {
    render(<Import />)
    expect(screen.getByTestId('cvs-upload-button')).toBeInTheDocument()
  })

  it('renders a generic CSV template download link', () => {
    render(<Import />)
    expect(screen.getByText('Download CSV template')).toBeInTheDocument()
  })

  it('calls importCvsPharmacy when a file is selected', async () => {
    ;(receiptsService.importCvsPharmacy as any).mockResolvedValue(makeResult())
    render(<Import />)

    const input = screen.getByTestId('cvs-file-input')
    const file = new File(['csv-data'], 'financial-summary.csv', { type: 'text/csv' })
    fireEvent.change(input, { target: { files: [file] } })

    await waitFor(() => {
      expect(receiptsService.importCvsPharmacy).toHaveBeenCalledWith(file)
    })
  })

  it('shows matched/unmatched counts after successful import', async () => {
    ;(receiptsService.importCvsPharmacy as any).mockResolvedValue(makeResult({ matched: 2, unmatched: 0, row_count: 2 }))
    render(<Import />)

    const input = screen.getByTestId('cvs-file-input')
    fireEvent.change(input, { target: { files: [new File(['x'], 'f.csv', { type: 'text/csv' })] } })

    await waitFor(() => {
      expect(screen.getByTestId('import-result')).toBeInTheDocument()
      expect(screen.getByText('2 matched')).toBeInTheDocument()
    })
  })

  it('shows drug names in the results table', async () => {
    ;(receiptsService.importCvsPharmacy as any).mockResolvedValue(makeResult())
    render(<Import />)

    fireEvent.change(screen.getByTestId('cvs-file-input'), {
      target: { files: [new File(['x'], 'f.csv', { type: 'text/csv' })] },
    })

    await waitFor(() => {
      expect(screen.getByText('WIXELA 250-50 INHUB')).toBeInTheDocument()
      expect(screen.getByText('LISINOPRIL 10MG')).toBeInTheDocument()
    })
  })

  it('shows unmatched badge when a fill has no transaction', async () => {
    ;(receiptsService.importCvsPharmacy as any).mockResolvedValue(makeResult({ matched: 1, unmatched: 1 }))
    render(<Import />)

    fireEvent.change(screen.getByTestId('cvs-file-input'), {
      target: { files: [new File(['x'], 'f.csv', { type: 'text/csv' })] },
    })

    await waitFor(() => {
      expect(screen.getByText('Unmatched')).toBeInTheDocument()
      expect(screen.getByText('1 unmatched')).toBeInTheDocument()
    })
  })

  it('shows error message when import fails', async () => {
    ;(receiptsService.importCvsPharmacy as any).mockRejectedValue({
      response: { data: { detail: 'Could not find the data header row.' } },
    })
    render(<Import />)

    fireEvent.change(screen.getByTestId('cvs-file-input'), {
      target: { files: [new File(['x'], 'f.csv', { type: 'text/csv' })] },
    })

    await waitFor(() => {
      expect(screen.getByTestId('import-error')).toBeInTheDocument()
      expect(screen.getByText('Could not find the data header row.')).toBeInTheDocument()
    })
  })
})
