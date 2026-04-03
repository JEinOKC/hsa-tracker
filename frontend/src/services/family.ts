import api from './api'

export interface EligibilityPeriod {
  id: string
  family_member_id: string
  start_date: string
  end_date: string | null
  notes: string | null
  created_at: string
}

export interface FamilyMember {
  id: string
  household_id: string
  name: string
  member_relationship: 'self' | 'spouse' | 'child' | 'other'
  linked_user_id: string | null
  date_of_birth: string | null
  is_tax_dependent: boolean
  is_active: boolean
  created_at: string
  updated_at: string
  eligibility_periods: EligibilityPeriod[]
}

export interface FamilyMemberCreate {
  name: string
  member_relationship: string
  date_of_birth?: string | null
  is_tax_dependent?: boolean
  eligibility_start?: string | null
  eligibility_end?: string | null
}

export interface FamilyMemberUpdate {
  name?: string
  member_relationship?: string
  date_of_birth?: string | null
  is_tax_dependent?: boolean
  is_active?: boolean
}

export interface EligibilityPeriodCreate {
  start_date: string
  end_date?: string | null
  notes?: string | null
}

export interface EligibilityCheckResult {
  member_id: string
  expense_date: string
  is_eligible: boolean
  matched_period: EligibilityPeriod | null
}

export const familyService = {
  list: (includeInactive = false) =>
    api.get<FamilyMember[]>('/families/', { params: { include_inactive: includeInactive } }).then(r => r.data),

  create: (payload: FamilyMemberCreate) =>
    api.post<FamilyMember>('/families/', payload).then(r => r.data),

  get: (id: string) =>
    api.get<FamilyMember>(`/families/${id}`).then(r => r.data),

  update: (id: string, payload: FamilyMemberUpdate) =>
    api.put<FamilyMember>(`/families/${id}`, payload).then(r => r.data),

  deactivate: (id: string) =>
    api.delete(`/families/${id}`),

  listEligibility: (memberId: string) =>
    api.get<EligibilityPeriod[]>(`/families/${memberId}/eligibility`).then(r => r.data),

  addEligibility: (memberId: string, payload: EligibilityPeriodCreate) =>
    api.post<EligibilityPeriod>(`/families/${memberId}/eligibility`, payload).then(r => r.data),

  updateEligibility: (memberId: string, periodId: string, payload: Partial<EligibilityPeriodCreate>) =>
    api.put<EligibilityPeriod>(`/families/${memberId}/eligibility/${periodId}`, payload).then(r => r.data),

  deleteEligibility: (memberId: string, periodId: string) =>
    api.delete(`/families/${memberId}/eligibility/${periodId}`),

  checkEligibility: (memberId: string, expenseDate: string) =>
    api.get<EligibilityCheckResult>(`/families/${memberId}/eligibility/check`, {
      params: { expense_date: expenseDate },
    }).then(r => r.data),
}
