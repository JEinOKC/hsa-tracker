import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '../../test/utils'
import MerchantManager from '../MerchantManager'

vi.mock('../../services/bank', () => ({
  bankService: {
    listMerchants: vi.fn(),
  },
}))

vi.mock('../../services/rules', () => ({
  rulesService: {
    create: vi.fn(),
    applyAll: vi.fn(),
  },
}))

import { bankService } from '../../services/bank'
import { rulesService } from '../../services/rules'

const makeMerchant = (overrides = {}) => ({
  normalized_name: 'MCDONALD\'S',
  transaction_count: 5,
  total_amount: '42.50',
  first_seen: '2026-01-01',
  last_seen: '2026-03-01',
  has_hsa: false,
  hsa_likelihood: 'unlikely' as const,
  ...overrides,
})

beforeEach(() => {
  vi.clearAllMocks()
  ;(bankService.listMerchants as any).mockResolvedValue([])
  ;(rulesService.create as any).mockResolvedValue({})
  ;(rulesService.applyAll as any).mockResolvedValue({ updated: 0 })
})

describe('MerchantManager', () => {
  it('shows loading state initially', () => {
    ;(bankService.listMerchants as any).mockReturnValue(new Promise(() => {}))
    render(<MerchantManager onClose={() => {}} onHidden={() => {}} />)
    expect(screen.getByText('Loading…')).toBeInTheDocument()
  })

  it('shows empty state when no merchants', async () => {
    render(<MerchantManager onClose={() => {}} onHidden={() => {}} />)
    await waitFor(() => {
      expect(screen.getByText('No merchants found.')).toBeInTheDocument()
    })
  })

  it('renders merchants grouped by section', async () => {
    ;(bankService.listMerchants as any).mockResolvedValue([
      makeMerchant({ normalized_name: 'MCDONALD\'S', hsa_likelihood: 'unlikely' }),
      makeMerchant({ normalized_name: 'CVS PHARMACY', hsa_likelihood: 'likely' }),
      makeMerchant({ normalized_name: 'AMAZON', hsa_likelihood: 'unknown' }),
    ])
    render(<MerchantManager onClose={() => {}} onHidden={() => {}} />)
    await waitFor(() => {
      expect(screen.getByText('MCDONALD\'S')).toBeInTheDocument()
      expect(screen.getByText('CVS PHARMACY')).toBeInTheDocument()
      expect(screen.getByText('AMAZON')).toBeInTheDocument()
    })
    expect(screen.getByText('Likely noise')).toBeInTheDocument()
    expect(screen.getByText('Possible medical')).toBeInTheDocument()
    expect(screen.getByText('Uncategorized')).toBeInTheDocument()
  })

  it('shows error when load fails', async () => {
    ;(bankService.listMerchants as any).mockRejectedValue(new Error('network'))
    render(<MerchantManager onClose={() => {}} onHidden={() => {}} />)
    await waitFor(() => {
      expect(screen.getByText('Failed to load merchants')).toBeInTheDocument()
    })
  })

  it('calls onClose when backdrop is clicked', async () => {
    const onClose = vi.fn()
    render(<MerchantManager onClose={onClose} onHidden={() => {}} />)
    await waitFor(() => screen.getByText('Manage Merchants'))
    // The backdrop is the first div with onClick=onClose
    fireEvent.click(document.querySelector('.absolute.inset-0.bg-black\\/30')!)
    expect(onClose).toHaveBeenCalled()
  })

  it('calls onClose when × button is clicked', async () => {
    const onClose = vi.fn()
    render(<MerchantManager onClose={onClose} onHidden={() => {}} />)
    await waitFor(() => screen.getByLabelText('Close'))
    fireEvent.click(screen.getByLabelText('Close'))
    expect(onClose).toHaveBeenCalled()
  })

  it('filters merchants by search input', async () => {
    ;(bankService.listMerchants as any).mockResolvedValue([
      makeMerchant({ normalized_name: 'MCDONALD\'S', hsa_likelihood: 'unlikely' }),
      makeMerchant({ normalized_name: 'STARBUCKS', hsa_likelihood: 'unlikely' }),
    ])
    render(<MerchantManager onClose={() => {}} onHidden={() => {}} />)
    await waitFor(() => screen.getByText('MCDONALD\'S'))

    fireEvent.change(screen.getByPlaceholderText('Search merchants…'), {
      target: { value: 'star' },
    })

    expect(screen.queryByText('MCDONALD\'S')).not.toBeInTheDocument()
    expect(screen.getByText('STARBUCKS')).toBeInTheDocument()
  })

  it('shows no-match message when search has no results', async () => {
    ;(bankService.listMerchants as any).mockResolvedValue([
      makeMerchant({ normalized_name: 'MCDONALD\'S' }),
    ])
    render(<MerchantManager onClose={() => {}} onHidden={() => {}} />)
    await waitFor(() => screen.getByText('MCDONALD\'S'))

    fireEvent.change(screen.getByPlaceholderText('Search merchants…'), {
      target: { value: 'zzznomatch' },
    })

    expect(screen.getByText('No merchants match your search.')).toBeInTheDocument()
  })

  describe('Hide all', () => {
    it('creates rule and calls onHidden for non-HSA merchant', async () => {
      const onHidden = vi.fn()
      ;(bankService.listMerchants as any).mockResolvedValue([
        makeMerchant({ normalized_name: 'MCDONALD\'S', has_hsa: false }),
      ])
      render(<MerchantManager onClose={() => {}} onHidden={onHidden} />)
      await waitFor(() => screen.getByText('MCDONALD\'S'))

      fireEvent.click(screen.getByRole('button', { name: 'Hide all' }))

      await waitFor(() => {
        expect(rulesService.create).toHaveBeenCalledWith(
          expect.objectContaining({
            name: "Hide MCDONALD'S",
            is_active: true,
          })
        )
        expect(rulesService.applyAll).toHaveBeenCalled()
        expect(onHidden).toHaveBeenCalled()
      })
    })

    it('removes merchant from list after hiding', async () => {
      ;(bankService.listMerchants as any).mockResolvedValue([
        makeMerchant({ normalized_name: 'MCDONALD\'S', has_hsa: false }),
      ])
      render(<MerchantManager onClose={() => {}} onHidden={() => {}} />)
      await waitFor(() => screen.getByText('MCDONALD\'S'))

      fireEvent.click(screen.getByRole('button', { name: 'Hide all' }))

      await waitFor(() => {
        expect(screen.queryByText('MCDONALD\'S')).not.toBeInTheDocument()
      })
    })

    it('shows HSA warning dialog before hiding a merchant with HSA transactions', async () => {
      ;(bankService.listMerchants as any).mockResolvedValue([
        makeMerchant({ normalized_name: 'CVS PHARMACY', has_hsa: true, transaction_count: 3 }),
      ])
      render(<MerchantManager onClose={() => {}} onHidden={() => {}} />)
      await waitFor(() => screen.getByText('CVS PHARMACY'))

      fireEvent.click(screen.getByRole('button', { name: 'Hide all' }))

      expect(screen.getByText('HSA transactions exist for this merchant')).toBeInTheDocument()
      expect(rulesService.create).not.toHaveBeenCalled()
    })

    it('proceeds with hide after confirming HSA warning', async () => {
      const onHidden = vi.fn()
      ;(bankService.listMerchants as any).mockResolvedValue([
        makeMerchant({ normalized_name: 'CVS PHARMACY', has_hsa: true }),
      ])
      render(<MerchantManager onClose={() => {}} onHidden={onHidden} />)
      await waitFor(() => screen.getByText('CVS PHARMACY'))

      fireEvent.click(screen.getByRole('button', { name: 'Hide all' }))
      await waitFor(() => screen.getByText('Hide anyway'))
      fireEvent.click(screen.getByRole('button', { name: 'Hide anyway' }))

      await waitFor(() => {
        expect(rulesService.create).toHaveBeenCalled()
        expect(onHidden).toHaveBeenCalled()
      })
    })

    it('cancels hide from HSA warning dialog', async () => {
      ;(bankService.listMerchants as any).mockResolvedValue([
        makeMerchant({ normalized_name: 'CVS PHARMACY', has_hsa: true }),
      ])
      render(<MerchantManager onClose={() => {}} onHidden={() => {}} />)
      await waitFor(() => screen.getByText('CVS PHARMACY'))

      fireEvent.click(screen.getByRole('button', { name: 'Hide all' }))
      await waitFor(() => screen.getByText('Hide anyway'))
      fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

      expect(rulesService.create).not.toHaveBeenCalled()
      expect(screen.queryByText('Hide anyway')).not.toBeInTheDocument()
    })

    it('shows error when hide fails', async () => {
      ;(rulesService.create as any).mockRejectedValue(new Error('network'))
      ;(bankService.listMerchants as any).mockResolvedValue([
        makeMerchant({ normalized_name: 'MCDONALD\'S', has_hsa: false }),
      ])
      render(<MerchantManager onClose={() => {}} onHidden={() => {}} />)
      await waitFor(() => screen.getByText('MCDONALD\'S'))

      fireEvent.click(screen.getByRole('button', { name: 'Hide all' }))

      await waitFor(() => {
        expect(screen.getByText(/Failed to hide MCDONALD'S/)).toBeInTheDocument()
      })
    })
  })
})
