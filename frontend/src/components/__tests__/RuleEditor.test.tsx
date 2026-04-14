import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '../../test/utils'
import RuleEditor from '../RuleEditor'

vi.mock('../../services/rules', () => ({
  rulesService: {
    create: vi.fn(),
    update: vi.fn(),
  },
}))

import { rulesService } from '../../services/rules'

const mockMembers = [
  { id: 'mem-1', name: 'Jane', household_id: 'hh-1', member_relationship: 'spouse' as const, linked_user_id: null, date_of_birth: null, is_tax_dependent: false, is_active: true, created_at: '', updated_at: '', eligibility_periods: [] },
]

const mockRule = {
  id: 'rule-1',
  user_id: 'user-1',
  name: 'Pharmacy Rule',
  priority: 0,
  is_active: true,
  conditions: [{ id: 'c1', rule_id: 'rule-1', field: 'description' as const, operator: 'contains' as const, value: 'CVS', created_at: '' }],
  actions: [{ id: 'a1', rule_id: 'rule-1', action_type: 'mark_hsa' as const, member_id: null, created_at: '' }],
  created_at: '',
  updated_at: '',
}

const noop = () => {}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('RuleEditor', () => {
  it('renders with empty state for new rule', () => {
    render(<RuleEditor rule={null} members={[]} onSave={noop} onClose={noop} />)
    expect(screen.getByText('New Rule')).toBeInTheDocument()
  })

  it('renders with existing rule data when editing', () => {
    render(<RuleEditor rule={mockRule} members={[]} onSave={noop} onClose={noop} />)
    expect(screen.getByText('Edit Rule')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Pharmacy Rule')).toBeInTheDocument()
  })

  it('shows condition rows with field, operator, value inputs', () => {
    render(<RuleEditor rule={null} members={[]} onSave={noop} onClose={noop} />)
    expect(screen.getByDisplayValue('Description')).toBeInTheDocument()
    expect(screen.getByDisplayValue('contains')).toBeInTheDocument()
  })

  it('shows action rows with action_type dropdown', () => {
    render(<RuleEditor rule={null} members={[]} onSave={noop} onClose={noop} />)
    expect(screen.getByDisplayValue('Mark as HSA eligible')).toBeInTheDocument()
  })

  it('shows Save Rule and Cancel buttons', () => {
    render(<RuleEditor rule={null} members={[]} onSave={noop} onClose={noop} />)
    expect(screen.getByRole('button', { name: 'Save Rule' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
  })

  it('calls onClose when Cancel is clicked', () => {
    const onClose = vi.fn()
    render(<RuleEditor rule={null} members={[]} onSave={noop} onClose={onClose} />)
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onClose).toHaveBeenCalled()
  })

  it('shows error when saving with empty name', async () => {
    render(<RuleEditor rule={null} members={[]} onSave={noop} onClose={noop} />)
    fireEvent.click(screen.getByRole('button', { name: 'Save Rule' }))
    await waitFor(() => {
      expect(screen.getByText('Name is required.')).toBeInTheDocument()
    })
  })

  it('shows error when condition value is empty', async () => {
    render(<RuleEditor rule={null} members={[]} onSave={noop} onClose={noop} />)
    fireEvent.change(screen.getByPlaceholderText('e.g. Flag pharmacy transactions'), {
      target: { value: 'My Rule' },
    })
    // Value input is empty by default
    fireEvent.click(screen.getByRole('button', { name: 'Save Rule' }))
    await waitFor(() => {
      expect(screen.getByText('All condition values must be filled in.')).toBeInTheDocument()
    })
  })

  it('calls rulesService.create with correct payload for new rule', async () => {
    const savedRule = { ...mockRule, id: 'new-rule' }
    ;(rulesService.create as ReturnType<typeof vi.fn>).mockResolvedValue(savedRule)
    const onSave = vi.fn()

    render(<RuleEditor rule={null} members={[]} onSave={onSave} onClose={noop} />)

    fireEvent.change(screen.getByPlaceholderText('e.g. Flag pharmacy transactions'), {
      target: { value: 'Test Rule' },
    })
    // Fill in condition value
    fireEvent.change(screen.getByPlaceholderText('value…'), { target: { value: 'CVS' } })

    fireEvent.click(screen.getByRole('button', { name: 'Save Rule' }))

    await waitFor(() => {
      expect(rulesService.create).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Test Rule',
          conditions: [expect.objectContaining({ value: 'CVS' })],
        })
      )
      expect(onSave).toHaveBeenCalledWith(savedRule)
    })
  })

  it('calls rulesService.update when editing existing rule', async () => {
    ;(rulesService.update as ReturnType<typeof vi.fn>).mockResolvedValue(mockRule)
    const onSave = vi.fn()

    render(<RuleEditor rule={mockRule} members={[]} onSave={onSave} onClose={noop} />)
    fireEvent.click(screen.getByRole('button', { name: 'Save Rule' }))

    await waitFor(() => {
      expect(rulesService.update).toHaveBeenCalledWith('rule-1', expect.any(Object))
      expect(onSave).toHaveBeenCalled()
    })
  })

  it('shows error message when save fails', async () => {
    ;(rulesService.create as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Network error'))

    render(<RuleEditor rule={null} members={[]} onSave={noop} onClose={noop} />)
    fireEvent.change(screen.getByPlaceholderText('e.g. Flag pharmacy transactions'), {
      target: { value: 'Test Rule' },
    })
    fireEvent.change(screen.getByPlaceholderText('value…'), { target: { value: 'CVS' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save Rule' }))

    await waitFor(() => {
      expect(screen.getByText(/failed to save rule/i)).toBeInTheDocument()
    })
  })

  it('can add a second condition row', () => {
    render(<RuleEditor rule={null} members={[]} onSave={noop} onClose={noop} />)
    fireEvent.click(screen.getByText('+ Add condition'))
    const valueInputs = screen.getAllByPlaceholderText('value…')
    expect(valueInputs.length).toBe(2)
  })

  it('can remove a condition row when there are multiple', () => {
    render(<RuleEditor rule={null} members={[]} onSave={noop} onClose={noop} />)
    fireEvent.click(screen.getByText('+ Add condition'))
    const removeButtons = screen.getAllByRole('button', { name: 'Remove condition' })
    expect(removeButtons.length).toBeGreaterThanOrEqual(1)
    fireEvent.click(removeButtons[0])
    const valueInputs = screen.getAllByPlaceholderText('value…')
    expect(valueInputs.length).toBe(1)
  })

  it('shows amount operator options when Amount field is selected', () => {
    render(<RuleEditor rule={null} members={[]} onSave={noop} onClose={noop} />)
    fireEvent.change(screen.getByDisplayValue('Description'), { target: { value: 'amount' } })
    expect(screen.getByDisplayValue('equals')).toBeInTheDocument()
  })

  it('shows date operator options when Date field is selected', () => {
    render(<RuleEditor rule={null} members={[]} onSave={noop} onClose={noop} />)
    fireEvent.change(screen.getByDisplayValue('Description'), { target: { value: 'date' } })
    expect(screen.getByDisplayValue('before')).toBeInTheDocument()
  })

  it('shows family member picker when assign_member action is selected', () => {
    render(<RuleEditor rule={null} members={mockMembers} onSave={noop} onClose={noop} />)
    fireEvent.change(screen.getByDisplayValue('Mark as HSA eligible'), {
      target: { value: 'assign_member' },
    })
    expect(screen.getByDisplayValue('— select member —')).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Jane' })).toBeInTheDocument()
  })

  it('hides family member picker when action type is not assign_member', () => {
    render(<RuleEditor rule={null} members={mockMembers} onSave={noop} onClose={noop} />)
    // Default is mark_hsa, no member picker
    expect(screen.queryByDisplayValue('— select member —')).not.toBeInTheDocument()
  })

  it('shows placement toggle for new rules', () => {
    render(<RuleEditor rule={null} members={[]} onSave={noop} onClose={noop} />)
    expect(screen.getByText('Apply before existing rules')).toBeInTheDocument()
    expect(screen.getByText('Apply after existing rules')).toBeInTheDocument()
  })

  it('does not show placement toggle when editing an existing rule', () => {
    render(<RuleEditor rule={mockRule} members={[]} onSave={noop} onClose={noop} />)
    expect(screen.queryByText('Apply before existing rules')).not.toBeInTheDocument()
    expect(screen.queryByText('Apply after existing rules')).not.toBeInTheDocument()
  })

  it('sends placement=first when "Apply before existing rules" is selected', async () => {
    ;(rulesService.create as any).mockResolvedValue({ ...mockRule, id: 'new-1' })
    render(<RuleEditor rule={null} members={[]} onSave={noop} onClose={noop} />)
    fireEvent.change(screen.getByPlaceholderText('e.g. Flag pharmacy transactions'), { target: { value: 'Test Rule' } })
    fireEvent.change(screen.getByPlaceholderText('value…'), { target: { value: 'CVS' } })
    fireEvent.click(screen.getByText('Apply before existing rules'))
    fireEvent.click(screen.getByText('Save Rule'))
    await waitFor(() => {
      expect(rulesService.create).toHaveBeenCalledWith(expect.objectContaining({ placement: 'first' }))
    })
  })

  it('sends placement=last when "Apply after existing rules" is selected', async () => {
    ;(rulesService.create as any).mockResolvedValue({ ...mockRule, id: 'new-1' })
    render(<RuleEditor rule={null} members={[]} onSave={noop} onClose={noop} />)
    fireEvent.change(screen.getByPlaceholderText('e.g. Flag pharmacy transactions'), { target: { value: 'Test Rule' } })
    fireEvent.change(screen.getByPlaceholderText('value…'), { target: { value: 'CVS' } })
    fireEvent.click(screen.getByText('Apply after existing rules'))
    fireEvent.click(screen.getByText('Save Rule'))
    await waitFor(() => {
      expect(rulesService.create).toHaveBeenCalledWith(expect.objectContaining({ placement: 'last' }))
    })
  })

  it('active toggle is on by default', () => {
    render(<RuleEditor rule={null} members={[]} onSave={noop} onClose={noop} />)
    expect(screen.getByRole('button', { name: '' })).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('toggles active state when toggle is clicked', () => {
    render(<RuleEditor rule={null} members={[]} onSave={noop} onClose={noop} />)
    const toggle = screen.getByRole('button', { name: '' })
    // Initial state: Active
    expect(screen.getByText('Active')).toBeInTheDocument()
    fireEvent.click(toggle)
    expect(screen.getByText('Inactive')).toBeInTheDocument()
  })
})