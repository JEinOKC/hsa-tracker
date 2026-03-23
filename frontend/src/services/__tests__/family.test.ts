import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

import api from '../api'
import { familyService } from '../family'

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

const mockPeriod = {
  id: 'period-uuid-1',
  family_member_id: 'member-uuid-1',
  start_date: '2024-01-01',
  end_date: null,
  notes: null,
  created_at: '2026-03-22T00:00:00',
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('familyService.list', () => {
  it('calls GET /families/ without params by default', async () => {
    ;(api.get as any).mockResolvedValue({ data: [mockMember] })

    const result = await familyService.list()

    expect(api.get).toHaveBeenCalledWith('/families/', { params: { include_inactive: false } })
    expect(result).toHaveLength(1)
  })

  it('passes include_inactive=true when requested', async () => {
    ;(api.get as any).mockResolvedValue({ data: [] })

    await familyService.list(true)

    expect(api.get).toHaveBeenCalledWith('/families/', { params: { include_inactive: true } })
  })
})

describe('familyService.create', () => {
  it('POSTs payload and returns created member', async () => {
    ;(api.post as any).mockResolvedValue({ data: mockMember })

    const result = await familyService.create({
      name: 'Jane Doe',
      member_relationship: 'spouse',
      is_tax_dependent: false,
    })

    expect(api.post).toHaveBeenCalledWith('/families/', {
      name: 'Jane Doe',
      member_relationship: 'spouse',
      is_tax_dependent: false,
    })
    expect(result.name).toBe('Jane Doe')
    expect(result.member_relationship).toBe('spouse')
  })
})

describe('familyService.get', () => {
  it('calls GET /families/:id', async () => {
    ;(api.get as any).mockResolvedValue({ data: mockMember })

    const result = await familyService.get('member-uuid-1')

    expect(api.get).toHaveBeenCalledWith('/families/member-uuid-1')
    expect(result.id).toBe('member-uuid-1')
  })
})

describe('familyService.update', () => {
  it('PUTs updated fields', async () => {
    const updated = { ...mockMember, name: 'Jane Smith' }
    ;(api.put as any).mockResolvedValue({ data: updated })

    const result = await familyService.update('member-uuid-1', { name: 'Jane Smith' })

    expect(api.put).toHaveBeenCalledWith('/families/member-uuid-1', { name: 'Jane Smith' })
    expect(result.name).toBe('Jane Smith')
  })
})

describe('familyService.deactivate', () => {
  it('calls DELETE /families/:id', async () => {
    ;(api.delete as any).mockResolvedValue({})

    await familyService.deactivate('member-uuid-1')

    expect(api.delete).toHaveBeenCalledWith('/families/member-uuid-1')
  })
})

describe('familyService.addEligibility', () => {
  it('POSTs eligibility period', async () => {
    ;(api.post as any).mockResolvedValue({ data: mockPeriod })

    const result = await familyService.addEligibility('member-uuid-1', {
      start_date: '2024-01-01',
      end_date: null,
    })

    expect(api.post).toHaveBeenCalledWith('/families/member-uuid-1/eligibility', {
      start_date: '2024-01-01',
      end_date: null,
    })
    expect(result.start_date).toBe('2024-01-01')
    expect(result.end_date).toBeNull()
  })
})

describe('familyService.deleteEligibility', () => {
  it('calls DELETE on the period', async () => {
    ;(api.delete as any).mockResolvedValue({})

    await familyService.deleteEligibility('member-uuid-1', 'period-uuid-1')

    expect(api.delete).toHaveBeenCalledWith('/families/member-uuid-1/eligibility/period-uuid-1')
  })
})

describe('familyService.checkEligibility', () => {
  it('calls GET with expense_date param', async () => {
    const checkResult = {
      member_id: 'member-uuid-1',
      expense_date: '2025-03-15',
      is_eligible: true,
      matched_period: mockPeriod,
    }
    ;(api.get as any).mockResolvedValue({ data: checkResult })

    const result = await familyService.checkEligibility('member-uuid-1', '2025-03-15')

    expect(api.get).toHaveBeenCalledWith('/families/member-uuid-1/eligibility/check', {
      params: { expense_date: '2025-03-15' },
    })
    expect(result.is_eligible).toBe(true)
    expect(result.matched_period).not.toBeNull()
  })

  it('returns not eligible with null period', async () => {
    ;(api.get as any).mockResolvedValue({
      data: { member_id: 'member-uuid-1', expense_date: '2020-01-01', is_eligible: false, matched_period: null },
    })

    const result = await familyService.checkEligibility('member-uuid-1', '2020-01-01')

    expect(result.is_eligible).toBe(false)
    expect(result.matched_period).toBeNull()
  })
})
