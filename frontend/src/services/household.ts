import api from './api'

export interface Household {
  id: string
  name: string
  created_by_id: string
  strict_eligibility: boolean
  is_admin: boolean
}

export const householdService = {
  getMine: (): Promise<Household | null> =>
    api.get<{ household: Household; is_admin: boolean }>('/households/mine')
      .then(r => ({ ...r.data.household, is_admin: r.data.is_admin }))
      .catch(() => null),

  updateSettings: (strict_eligibility: boolean): Promise<Household> =>
    api.patch<{ household: Household; is_admin: boolean }>('/households/mine', { strict_eligibility })
      .then(r => ({ ...r.data.household, is_admin: r.data.is_admin })),
}
