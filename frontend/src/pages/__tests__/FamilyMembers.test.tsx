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

vi.mock('../../services/familyInvites', () => ({
  default: {
    list: vi.fn().mockResolvedValue([]),
    create: vi.fn(),
    revoke: vi.fn(),
    validate: vi.fn(),
    getFamilyPin: vi.fn().mockResolvedValue('1234'),
    resetFamilyPin: vi.fn(),
  },
}))

vi.mock('../../services/households', () => ({
  default: {
    getMine: vi.fn(),
    create: vi.fn(),
    createRole: vi.fn(),
    updateRole: vi.fn(),
    deleteRole: vi.fn(),
    removeMember: vi.fn(),
    transferAdmin: vi.fn(),
  },
}))

vi.mock('../../store/authStore', () => ({
  useAuthStore: () => ({ user: { id: 'current-user-id' } }),
}))

import { familyService } from '../../services/family'
import familyInvitesService from '../../services/familyInvites'
import householdsService from '../../services/households'

const mockMember = {
  id: 'member-uuid-1',
  user_id: 'user-uuid-1',
  name: 'Jane Doe',
  member_relationship: 'spouse' as const,
  linked_user_id: null,
  date_of_birth: '1985-06-15',
  is_tax_dependent: false,
  is_active: true,
  created_at: '2026-03-22T00:00:00',
  updated_at: '2026-03-22T00:00:00',
  eligibility_periods: [],
}

const mockMemberSelf = {
  ...mockMember,
  id: 'member-uuid-self',
  name: 'James England',
  member_relationship: 'self' as const,
  linked_user_id: 'current-user-id',
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

const mockHouseholdRole = {
  id: 'hh-role-uuid-1',
  household_id: 'hh-uuid-1',
  name: 'Spouse',
  can_read_transactions: true,
  can_write_transactions: true,
  can_delete_transactions: false,
  can_read_bank_accounts: true,
  can_write_bank_accounts: false,
  can_delete_bank_accounts: false,
  can_read_documents: true,
  can_write_documents: false,
  can_delete_documents: false,
  can_read_family_members: true,
  can_write_family_members: false,
  can_delete_family_members: false,
  created_at: '2026-04-01T00:00:00',
}

const mockHouseholdDetail = {
  household: { id: 'hh-uuid-1', name: 'England Family', created_by_id: 'user-uuid-1', created_at: '2026-04-01T00:00:00' },
  roles: [mockHouseholdRole],
  members: [{
    id: 'mem-uuid-1',
    household_id: 'hh-uuid-1',
    user_id: 'user-uuid-1',
    username: 'james',
    display_name: 'James',
    role: mockHouseholdRole,
    is_admin: true,
    joined_at: '2026-04-01T00:00:00',
  }],
}

beforeEach(() => {
  vi.clearAllMocks()
  ;(familyService.list as any).mockResolvedValue([])
  ;(householdsService.getMine as any).mockRejectedValue({ response: { status: 404 } })
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
      expect(screen.getByText(/no members tracked yet/i)).toBeInTheDocument()
    })
  })

  it('shows Add Member button', async () => {
    render(<FamilyMembers />)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /\+ add member/i })).toBeInTheDocument()
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
    await waitFor(() => screen.getByRole('button', { name: /\+ add member/i }))

    fireEvent.click(screen.getByRole('button', { name: /\+ add member/i }))

    expect(screen.getByText('Add Family Member')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Full name')).toBeInTheDocument()
  })

  it('add form does NOT show account path options when no household exists', async () => {
    render(<FamilyMembers />)
    await waitFor(() => screen.getByRole('button', { name: /\+ add member/i }))

    fireEvent.click(screen.getByRole('button', { name: /\+ add member/i }))

    await waitFor(() => {
      expect(screen.queryByText(/account access/i)).not.toBeInTheDocument()
    })
  })

  it('add form shows account path options when household exists', async () => {
    ;(householdsService.getMine as any).mockResolvedValue(mockHouseholdDetail)
    render(<FamilyMembers />)
    await waitFor(() => screen.getByText('England Family'))

    fireEvent.click(screen.getByRole('button', { name: /\+ add member/i }))

    await waitFor(() => {
      expect(screen.getByText(/account access/i)).toBeInTheDocument()
      expect(screen.getByText(/send an invite link/i)).toBeInTheDocument()
      expect(screen.getByText(/no account needed/i)).toBeInTheDocument()
    })
  })

  it('add form shows role selector when invite path is selected', async () => {
    ;(householdsService.getMine as any).mockResolvedValue(mockHouseholdDetail)
    render(<FamilyMembers />)
    await waitFor(() => screen.getByText('England Family'))

    fireEvent.click(screen.getByRole('button', { name: /\+ add member/i }))
    await waitFor(() => screen.getByText(/send an invite link/i))

    const radios = screen.getAllByRole('radio')
    const inviteRadio = radios.find(r => (r as HTMLInputElement).value === 'invite')!
    fireEvent.click(inviteRadio)

    await waitFor(() => {
      // The household role select has a unique placeholder option distinct from the relationship dropdown
      expect(screen.getByRole('option', { name: 'Select a household role…' })).toBeInTheDocument()
    })
  })

  it('creates a member and calls familyService.create', async () => {
    ;(familyService.create as any).mockResolvedValue(mockMember)

    render(<FamilyMembers />)
    await waitFor(() => screen.getByRole('button', { name: /\+ add member/i }))

    fireEvent.click(screen.getByRole('button', { name: /\+ add member/i }))

    fireEvent.change(screen.getByPlaceholderText('Full name'), {
      target: { value: 'Jane Doe' },
    })

    fireEvent.click(screen.getByRole('button', { name: /^add member$/i, hidden: false }))

    await waitFor(() => {
      expect(familyService.create).toHaveBeenCalled()
    })
  })

  it('creates member + invite when invite path selected', async () => {
    ;(householdsService.getMine as any).mockResolvedValue(mockHouseholdDetail)
    ;(familyService.create as any).mockResolvedValue(mockMember)
    ;(familyInvitesService.create as any).mockResolvedValue({
      token: 'abc-def-ghi',
      label: null,
      invite_url: 'http://localhost/invite/abc-def-ghi',
      qr_code_data_url: 'data:image/png;base64,abc',
      expires_at: new Date(Date.now() + 72 * 3600000).toISOString(),
      require_pin: true,
      is_used: false,
    })

    render(<FamilyMembers />)
    await waitFor(() => screen.getByText('England Family'))

    fireEvent.click(screen.getByRole('button', { name: /\+ add member/i }))
    await waitFor(() => screen.getByText(/send an invite link/i))

    fireEvent.change(screen.getByPlaceholderText('Full name'), { target: { value: 'Jane Doe' } })

    const radios = screen.getAllByRole('radio')
    const inviteRadio = radios.find(r => (r as HTMLInputElement).value === 'invite')!
    fireEvent.click(inviteRadio)

    // Find role select via its unique placeholder option
    await waitFor(() => screen.getByRole('option', { name: 'Select a household role…' }))
    const roleOption = screen.getByRole('option', { name: 'Select a household role…' })
    fireEvent.change(roleOption.closest('select')!, { target: { value: 'hh-role-uuid-1' } })

    fireEvent.click(screen.getByRole('button', { name: /^add member$/i }))

    await waitFor(() => {
      expect(familyService.create).toHaveBeenCalled()
      expect(familyInvitesService.create).toHaveBeenCalledWith(undefined, true, 'hh-role-uuid-1', 'member-uuid-1')
    })
  })

  it('displays QR code image after invite is created', async () => {
    ;(householdsService.getMine as any).mockResolvedValue(mockHouseholdDetail)
    ;(familyService.create as any).mockResolvedValue(mockMember)
    ;(familyInvitesService.create as any).mockResolvedValue({
      token: 'abc-def-ghi',
      label: null,
      invite_url: 'http://localhost/invite/abc-def-ghi',
      qr_code_data_url: 'data:image/png;base64,abc',
      expires_at: new Date(Date.now() + 72 * 3600000).toISOString(),
      require_pin: true,
      is_used: false,
    })

    render(<FamilyMembers />)
    await waitFor(() => screen.getByText('England Family'))

    fireEvent.click(screen.getByRole('button', { name: /\+ add member/i }))
    await waitFor(() => screen.getByText(/send an invite link/i))

    fireEvent.change(screen.getByPlaceholderText('Full name'), { target: { value: 'Jane Doe' } })

    const radios = screen.getAllByRole('radio')
    const inviteRadio = radios.find(r => (r as HTMLInputElement).value === 'invite')!
    fireEvent.click(inviteRadio)

    await waitFor(() => screen.getByRole('option', { name: 'Select a household role…' }))
    const roleOption = screen.getByRole('option', { name: 'Select a household role…' })
    fireEvent.change(roleOption.closest('select')!, { target: { value: 'hh-role-uuid-1' } })

    fireEvent.click(screen.getByRole('button', { name: /^add member$/i }))

    await waitFor(() => {
      const qr = screen.getByAltText(/qr code for invite link/i)
      expect(qr).toBeInTheDocument()
      expect(qr).toHaveAttribute('src', 'data:image/png;base64,abc')
    })
  })

  it('hides add form after cancel', async () => {
    render(<FamilyMembers />)
    await waitFor(() => screen.getByRole('button', { name: /\+ add member/i }))

    fireEvent.click(screen.getByRole('button', { name: /\+ add member/i }))
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

    vi.spyOn(window, 'confirm').mockReturnValue(true)

    fireEvent.click(screen.getByRole('button', { name: /remove/i }))

    await waitFor(() => {
      expect(familyService.deactivate).toHaveBeenCalledWith('member-uuid-1')
      expect(screen.queryByText('Jane Doe')).not.toBeInTheDocument()
    })
  })

  it('shows "Invite to account" button for non-self member when household exists', async () => {
    ;(householdsService.getMine as any).mockResolvedValue(mockHouseholdDetail)
    ;(familyService.list as any).mockResolvedValue([mockMember])
    render(<FamilyMembers />)
    await waitFor(() => screen.getByText('Jane Doe'))

    expect(screen.getByRole('button', { name: /invite to account/i })).toBeInTheDocument()
  })

  it('does NOT show "Invite to account" button for self member', async () => {
    ;(householdsService.getMine as any).mockResolvedValue(mockHouseholdDetail)
    ;(familyService.list as any).mockResolvedValue([mockMemberSelf])
    render(<FamilyMembers />)
    await waitFor(() => screen.getByText('James England'))

    expect(screen.queryByRole('button', { name: /invite to account/i })).not.toBeInTheDocument()
  })

  it('does NOT show "Invite to account" button when no household exists', async () => {
    ;(familyService.list as any).mockResolvedValue([mockMember])
    render(<FamilyMembers />)
    await waitFor(() => screen.getByText('Jane Doe'))

    expect(screen.queryByRole('button', { name: /invite to account/i })).not.toBeInTheDocument()
  })
})


describe('Household setup', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(familyService.list as any).mockResolvedValue([])
  })

  it('shows household name as subtitle when household exists', async () => {
    ;(householdsService.getMine as any).mockResolvedValue(mockHouseholdDetail)
    render(<FamilyMembers />)
    await waitFor(() => {
      expect(screen.getByText('England Family')).toBeInTheDocument()
    })
  })

  it('shows household roles settings when household exists', async () => {
    ;(householdsService.getMine as any).mockResolvedValue(mockHouseholdDetail)
    render(<FamilyMembers />)
    await waitFor(() => {
      expect(screen.getAllByText('Spouse').length).toBeGreaterThan(0)
      expect(screen.getByRole('button', { name: /\+ new role/i })).toBeInTheDocument()
    })
  })

  it('no standalone invite panel shown (invites happen on member cards)', async () => {
    ;(householdsService.getMine as any).mockResolvedValue(mockHouseholdDetail)
    render(<FamilyMembers />)
    await waitFor(() => screen.getByText('England Family'))

    expect(screen.queryByRole('button', { name: /\+ new invite/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/invite a family member/i)).not.toBeInTheDocument()
  })

  it('does not show household settings section when no household', async () => {
    ;(householdsService.getMine as any).mockRejectedValue({ response: { status: 404 } })
    render(<FamilyMembers />)
    // Wait for household load to complete (empty state appears)
    await waitFor(() => screen.getByText(/no members tracked yet/i))

    expect(screen.queryByText(/household settings/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /\+ new role/i })).not.toBeInTheDocument()
  })
})
