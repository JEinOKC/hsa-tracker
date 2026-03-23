import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '../../test/utils'
import FamilyMembers from '../FamilyMembers'

vi.mock('../../services/family', () => ({
  familyService: {
    list: vi.fn(),
    create: vi.fn(),
    get: vi.fn(),
    update: vi.fn(),
    deactivate: vi.fn(),
    addEligibility: vi.fn(),
    deleteEligibility: vi.fn(),
    checkEligibility: vi.fn(),
  },
}))

import { familyService } from '../../services/family'

const today = new Date().toISOString().split('T')[0]

const mockMember = {
  id: 'member-uuid-1',
  user_id: 'user-uuid-1',
  name: 'Jane Doe',
  member_relationship: 'spouse' as const,
  date_of_birth: '1985-06-15',
  is_tax_dependent: false,
  is_active: true,
  created_at: '2026-03-22T00:00:00',
  updated_at: '2026-03-22T00:00:00',
  eligibility_periods: [],
}

const mockMemberEligible = {
  ...mockMember,
  eligibility_periods: [
    {
      id: 'period-uuid-1',
      family_member_id: 'member-uuid-1',
      start_date: '2024-01-01',
      end_date: null,
      notes: null,
      created_at: '2026-03-22T00:00:00',
    },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  ;(familyService.list as any).mockResolvedValue([])
})

describe('FamilyMembers page', () => {
  it('renders page title', async () => {
    render(<FamilyMembers />)
    await waitFor(() => {
      expect(screen.getByText('Family Members')).toBeInTheDocument()
    })
  })

  it('shows empty state when no members', async () => {
    render(<FamilyMembers />)
    await waitFor(() => {
      expect(screen.getByText(/no family members yet/i)).toBeInTheDocument()
    })
  })

  it('shows Add Member button', async () => {
    render(<FamilyMembers />)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /add member/i })).toBeInTheDocument()
    })
  })

  it('shows eligibility info banner', async () => {
    render(<FamilyMembers />)
    await waitFor(() => {
      expect(screen.getByText(/about eligibility periods/i)).toBeInTheDocument()
    })
  })

  it('renders family members from API', async () => {
    ;(familyService.list as any).mockResolvedValue([mockMember])
    render(<FamilyMembers />)
    await waitFor(() => {
      expect(screen.getByText('Jane Doe')).toBeInTheDocument()
      expect(screen.getByText('spouse')).toBeInTheDocument()
    })
  })

  it('shows HSA Eligible badge for member with active period', async () => {
    ;(familyService.list as any).mockResolvedValue([mockMemberEligible])
    render(<FamilyMembers />)
    await waitFor(() => {
      expect(screen.getByText('HSA Eligible')).toBeInTheDocument()
    })
  })

  it('shows Not Eligible badge for member with no periods', async () => {
    ;(familyService.list as any).mockResolvedValue([mockMember])
    render(<FamilyMembers />)
    await waitFor(() => {
      expect(screen.getByText('Not Eligible')).toBeInTheDocument()
    })
  })

  it('shows add form when Add Member is clicked', async () => {
    render(<FamilyMembers />)
    await waitFor(() => screen.getByRole('button', { name: /add member/i }))

    fireEvent.click(screen.getByRole('button', { name: /add member/i }))

    expect(screen.getByText('Add Family Member')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Full name')).toBeInTheDocument()
  })

  it('creates a member and shows it in the list', async () => {
    ;(familyService.create as any).mockResolvedValue(mockMember)

    render(<FamilyMembers />)
    await waitFor(() => screen.getByRole('button', { name: /add member/i }))

    fireEvent.click(screen.getByRole('button', { name: /add member/i }))

    fireEvent.change(screen.getByPlaceholderText('Full name'), {
      target: { value: 'Jane Doe' },
    })

    fireEvent.click(screen.getByRole('button', { name: /add member/i, hidden: false }))

    await waitFor(() => {
      expect(familyService.create).toHaveBeenCalled()
    })
  })

  it('hides add form after cancel', async () => {
    render(<FamilyMembers />)
    await waitFor(() => screen.getByRole('button', { name: /add member/i }))

    fireEvent.click(screen.getByRole('button', { name: /add member/i }))
    expect(screen.getByText('Add Family Member')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(screen.queryByText('Add Family Member')).not.toBeInTheDocument()
  })

  it('shows eligibility sub-panel when Eligibility button is clicked', async () => {
    ;(familyService.list as any).mockResolvedValue([mockMemberEligible])
    render(<FamilyMembers />)
    await waitFor(() => screen.getByText('Jane Doe'))

    fireEvent.click(screen.getByRole('button', { name: /eligibility/i }))

    expect(screen.getByText('HSA Eligibility Periods')).toBeInTheDocument()
    expect(screen.getByText(/2024/)).toBeInTheDocument()
  })

  it('shows error banner on load failure', async () => {
    ;(familyService.list as any).mockRejectedValue(new Error('Server error'))
    render(<FamilyMembers />)
    await waitFor(() => {
      expect(screen.getByText(/failed to load family members/i)).toBeInTheDocument()
    })
  })

  it('removes member from list after deactivation', async () => {
    ;(familyService.list as any).mockResolvedValue([mockMember])
    ;(familyService.deactivate as any).mockResolvedValue({})

    render(<FamilyMembers />)
    await waitFor(() => screen.getByText('Jane Doe'))

    // Confirm dialog
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    fireEvent.click(screen.getByRole('button', { name: /remove/i }))

    await waitFor(() => {
      expect(familyService.deactivate).toHaveBeenCalledWith('member-uuid-1')
      expect(screen.queryByText('Jane Doe')).not.toBeInTheDocument()
    })
  })
})
