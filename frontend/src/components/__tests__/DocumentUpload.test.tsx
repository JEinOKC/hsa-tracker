import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '../../test/utils'
import DocumentUpload from '../DocumentUpload'

// Capture the onDrop callback so tests can trigger uploads directly
let capturedOnDrop: ((files: File[]) => void) = () => {}

vi.mock('react-dropzone', () => ({
  useDropzone: ({ onDrop }: { onDrop: (files: File[]) => void }) => {
    capturedOnDrop = onDrop
    return {
      getRootProps: () => ({ 'data-testid': 'dropzone' }),
      getInputProps: () => ({}),
      isDragActive: false,
    }
  },
}))

// Pass images through unchanged so tests don't need a real canvas
vi.mock('browser-image-compression', () => ({
  default: vi.fn((file: File) => Promise.resolve(file)),
}))

vi.mock('../../services/documents', () => ({
  documentService: {
    list: vi.fn(),
    presign: vi.fn(),
    putToS3: vi.fn(),
    confirm: vi.fn(),
    delete: vi.fn(),
  },
}))

import { documentService } from '../../services/documents'

const makeDoc = (overrides = {}) => ({
  id: 'doc-1',
  transaction_id: 'txn-1',
  original_filename: 'receipt.jpg',
  content_type: 'image/jpeg',
  file_size_bytes: 51200,
  uploaded_at: '2026-03-01T00:00:00',
  url: 'https://s3.example.com/receipt.jpg',
  ...overrides,
})

const makeImageFile = (name = 'receipt.jpg', type = 'image/jpeg') =>
  new File(['img-data'], name, { type })

const makePdfFile = (name = 'receipt.pdf') =>
  new File(['pdf-data'], name, { type: 'application/pdf' })

beforeEach(() => {
  vi.clearAllMocks()
  ;(documentService.list as any).mockResolvedValue([])
})

describe('DocumentUpload', () => {
  it('renders the drop zone', async () => {
    render(<DocumentUpload transactionId="txn-1" onCountChange={() => {}} />)
    await waitFor(() => {
      expect(screen.getByTestId('dropzone')).toBeInTheDocument()
    })
  })

  it('shows empty state when no documents', async () => {
    render(<DocumentUpload transactionId="txn-1" onCountChange={() => {}} />)
    await waitFor(() => {
      expect(screen.getByText(/no receipts attached yet/i)).toBeInTheDocument()
    })
  })

  it('loads and renders existing documents on mount', async () => {
    ;(documentService.list as any).mockResolvedValue([makeDoc()])
    const onCountChange = vi.fn()
    render(<DocumentUpload transactionId="txn-1" onCountChange={onCountChange} />)
    await waitFor(() => {
      expect(screen.getByText('receipt.jpg')).toBeInTheDocument()
    })
    expect(onCountChange).toHaveBeenCalledWith(1)
  })

  it('shows formatted file size for existing document', async () => {
    ;(documentService.list as any).mockResolvedValue([makeDoc({ file_size_bytes: 51200 })])
    render(<DocumentUpload transactionId="txn-1" onCountChange={() => {}} />)
    await waitFor(() => {
      expect(screen.getByText('50.0 KB')).toBeInTheDocument()
    })
  })

  it('renders document as a link to its URL', async () => {
    ;(documentService.list as any).mockResolvedValue([makeDoc()])
    render(<DocumentUpload transactionId="txn-1" onCountChange={() => {}} />)
    await waitFor(() => {
      const link = screen.getByRole('link', { name: 'receipt.jpg' })
      expect(link).toHaveAttribute('href', 'https://s3.example.com/receipt.jpg')
      expect(link).toHaveAttribute('target', '_blank')
    })
  })

  it('does not show empty state when documents exist', async () => {
    ;(documentService.list as any).mockResolvedValue([makeDoc()])
    render(<DocumentUpload transactionId="txn-1" onCountChange={() => {}} />)
    await waitFor(() => screen.getByText('receipt.jpg'))
    expect(screen.queryByText(/no receipts attached yet/i)).not.toBeInTheDocument()
  })

  describe('upload flow', () => {
    it('calls presign → putToS3 → confirm in order for an image', async () => {
      const confirmed = makeDoc({ id: 'doc-new' })
      ;(documentService.presign as any).mockResolvedValue({
        document_id: 'doc-new',
        upload_url: 'https://s3.example.com/presigned',
        s3_key: 'dev/user/txn/file.jpg',
      })
      ;(documentService.putToS3 as any).mockResolvedValue({ ok: true })
      ;(documentService.confirm as any).mockResolvedValue(confirmed)

      const onCountChange = vi.fn()
      render(<DocumentUpload transactionId="txn-1" onCountChange={onCountChange} />)
      await waitFor(() => screen.getByTestId('dropzone'))

      const file = makeImageFile()
      await capturedOnDrop([file])

      await waitFor(() => {
        expect(documentService.presign).toHaveBeenCalledWith('txn-1', expect.objectContaining({
          filename: 'receipt.jpg',
          content_type: 'image/jpeg',
        }))
        expect(documentService.putToS3).toHaveBeenCalledWith(
          'https://s3.example.com/presigned',
          expect.anything(),
          'image/jpeg',
        )
        expect(documentService.confirm).toHaveBeenCalledWith('txn-1', 'doc-new')
      })
    })

    it('adds confirmed document to list after upload', async () => {
      const confirmed = makeDoc({ id: 'doc-new', original_filename: 'new-receipt.jpg' })
      ;(documentService.presign as any).mockResolvedValue({
        document_id: 'doc-new',
        upload_url: 'https://s3.example.com/presigned',
        s3_key: 'dev/user/txn/file.jpg',
      })
      ;(documentService.putToS3 as any).mockResolvedValue({ ok: true })
      ;(documentService.confirm as any).mockResolvedValue(confirmed)

      const onCountChange = vi.fn()
      render(<DocumentUpload transactionId="txn-1" onCountChange={onCountChange} />)
      await waitFor(() => screen.getByTestId('dropzone'))

      await capturedOnDrop([makeImageFile('new-receipt.jpg')])

      await waitFor(() => {
        expect(screen.getByText('new-receipt.jpg')).toBeInTheDocument()
      })
      // Called once on mount (0), once after upload (1)
      expect(onCountChange).toHaveBeenLastCalledWith(1)
    })

    it('does not compress PDF files', async () => {
      ;(documentService.presign as any).mockResolvedValue({
        document_id: 'doc-pdf',
        upload_url: 'https://s3.example.com/presigned',
        s3_key: 'dev/user/txn/file.pdf',
      })
      ;(documentService.putToS3 as any).mockResolvedValue({ ok: true })
      ;(documentService.confirm as any).mockResolvedValue(makeDoc({ id: 'doc-pdf', content_type: 'application/pdf' }))

      const imageCompression = (await import('browser-image-compression')).default

      render(<DocumentUpload transactionId="txn-1" onCountChange={() => {}} />)
      await waitFor(() => screen.getByTestId('dropzone'))

      await capturedOnDrop([makePdfFile()])

      await waitFor(() => expect(documentService.putToS3).toHaveBeenCalled())
      expect(imageCompression).not.toHaveBeenCalled()
    })

    it('shows error when presign fails', async () => {
      ;(documentService.presign as any).mockRejectedValue(new Error('Server error'))

      render(<DocumentUpload transactionId="txn-1" onCountChange={() => {}} />)
      await waitFor(() => screen.getByTestId('dropzone'))

      await capturedOnDrop([makeImageFile()])

      await waitFor(() => {
        expect(screen.getByText('Server error')).toBeInTheDocument()
      })
    })

    it('shows error when S3 PUT fails', async () => {
      ;(documentService.presign as any).mockResolvedValue({
        document_id: 'doc-1',
        upload_url: 'https://s3.example.com/presigned',
        s3_key: 'key',
      })
      ;(documentService.putToS3 as any).mockResolvedValue({ ok: false, status: 403, statusText: 'Forbidden' })

      render(<DocumentUpload transactionId="txn-1" onCountChange={() => {}} />)
      await waitFor(() => screen.getByTestId('dropzone'))

      await capturedOnDrop([makeImageFile()])

      await waitFor(() => {
        expect(screen.getByText(/S3 upload failed/i)).toBeInTheDocument()
      })
    })
  })

  describe('delete', () => {
    it('removes document from list on delete', async () => {
      ;(documentService.list as any).mockResolvedValue([makeDoc()])
      ;(documentService.delete as any).mockResolvedValue(undefined)
      const onCountChange = vi.fn()

      render(<DocumentUpload transactionId="txn-1" onCountChange={onCountChange} />)
      await waitFor(() => screen.getByText('receipt.jpg'))

      fireEvent.click(screen.getByRole('button', { name: 'Delete receipt.jpg' }))

      await waitFor(() => {
        expect(screen.queryByText('receipt.jpg')).not.toBeInTheDocument()
      })
      expect(documentService.delete).toHaveBeenCalledWith('txn-1', 'doc-1')
      expect(onCountChange).toHaveBeenLastCalledWith(0)
    })

    it('shows error when delete fails', async () => {
      ;(documentService.list as any).mockResolvedValue([makeDoc()])
      ;(documentService.delete as any).mockRejectedValue(new Error('Network error'))

      render(<DocumentUpload transactionId="txn-1" onCountChange={() => {}} />)
      await waitFor(() => screen.getByText('receipt.jpg'))

      fireEvent.click(screen.getByRole('button', { name: 'Delete receipt.jpg' }))

      await waitFor(() => {
        expect(screen.getByText(/failed to delete/i)).toBeInTheDocument()
      })
    })
  })
})
