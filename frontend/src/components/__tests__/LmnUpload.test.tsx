import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '../../test/utils'
import LmnUpload from '../LmnUpload'

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

vi.mock('browser-image-compression', () => ({
  default: vi.fn((file: File) => Promise.resolve(file)),
}))

vi.mock('../../services/lmn', () => ({
  lmnService: {
    list: vi.fn(),
    presign: vi.fn(),
    putToS3: vi.fn(),
    confirm: vi.fn(),
    delete: vi.fn(),
  },
}))

import { lmnService } from '../../services/lmn'

const makeLmn = (overrides = {}) => ({
  id: 'lmn-1',
  family_member_id: 'member-1',
  family_member_name: 'Test Member',
  original_filename: 'letter.pdf',
  content_type: 'application/pdf',
  file_size_bytes: 50000,
  label: null,
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
  ;(lmnService.list as any).mockResolvedValue([])
})

describe('LmnUpload', () => {
  it('renders the drop zone', async () => {
    render(<LmnUpload familyMemberId="member-1" />)
    await waitFor(() => {
      expect(screen.getByTestId('dropzone')).toBeInTheDocument()
    })
  })

  it('shows empty state when no LMNs', async () => {
    render(<LmnUpload familyMemberId="member-1" />)
    await waitFor(() => {
      expect(screen.getByText(/no letters of medical necessity attached/i)).toBeInTheDocument()
    })
  })

  it('loads and renders existing LMN documents on mount', async () => {
    ;(lmnService.list as any).mockResolvedValue([makeLmn({ label: 'Ortho LMN' })])
    render(<LmnUpload familyMemberId="member-1" />)
    await waitFor(() => {
      expect(screen.getByText('Ortho LMN')).toBeInTheDocument()
    })
  })

  it('falls back to filename when no label', async () => {
    ;(lmnService.list as any).mockResolvedValue([makeLmn()])
    render(<LmnUpload familyMemberId="member-1" />)
    await waitFor(() => {
      expect(screen.getByText('letter.pdf')).toBeInTheDocument()
    })
  })

  it('shows provider and date metadata', async () => {
    ;(lmnService.list as any).mockResolvedValue([
      makeLmn({ provider_name: 'Smith', issue_date: '2026-01-15', expiration_date: '2027-01-15' }),
    ])
    render(<LmnUpload familyMemberId="member-1" />)
    await waitFor(() => {
      expect(screen.getByText(/Dr\. Smith/)).toBeInTheDocument()
    })
  })

  describe('upload flow', () => {
    it('calls presign → putToS3 → confirm in order', async () => {
      const confirmed = makeLmn({ id: 'lmn-new' })
      ;(lmnService.presign as any).mockResolvedValue({
        lmn_id: 'lmn-new',
        upload_url: 'https://s3.example.com/presigned',
        s3_key: 'dev/user/lmn/member/file.pdf',
      })
      ;(lmnService.putToS3 as any).mockResolvedValue({ ok: true })
      ;(lmnService.confirm as any).mockResolvedValue(confirmed)

      render(<LmnUpload familyMemberId="member-1" />)
      await waitFor(() => screen.getByTestId('dropzone'))

      const file = new File(['pdf-data'], 'letter.pdf', { type: 'application/pdf' })
      await capturedOnDrop([file])

      await waitFor(() => {
        expect(lmnService.presign).toHaveBeenCalledWith('member-1', expect.objectContaining({
          filename: 'letter.pdf',
          content_type: 'application/pdf',
        }))
        expect(lmnService.putToS3).toHaveBeenCalledWith(
          'https://s3.example.com/presigned',
          expect.anything(),
          'application/pdf',
        )
        expect(lmnService.confirm).toHaveBeenCalledWith('member-1', 'lmn-new')
      })
    })

    it('shows error when upload fails', async () => {
      ;(lmnService.presign as any).mockRejectedValue(new Error('Server error'))

      render(<LmnUpload familyMemberId="member-1" />)
      await waitFor(() => screen.getByTestId('dropzone'))

      await capturedOnDrop([new File(['data'], 'letter.pdf', { type: 'application/pdf' })])

      await waitFor(() => {
        expect(screen.getByText('Server error')).toBeInTheDocument()
      })
    })
  })

  describe('delete', () => {
    it('removes LMN from list on delete', async () => {
      ;(lmnService.list as any).mockResolvedValue([makeLmn()])
      ;(lmnService.delete as any).mockResolvedValue(undefined)

      render(<LmnUpload familyMemberId="member-1" />)
      await waitFor(() => screen.getByText('letter.pdf'))

      fireEvent.click(screen.getByRole('button', { name: 'Delete letter.pdf' }))

      await waitFor(() => {
        expect(screen.queryByText('letter.pdf')).not.toBeInTheDocument()
      })
      expect(lmnService.delete).toHaveBeenCalledWith('member-1', 'lmn-1')
    })
  })
})
