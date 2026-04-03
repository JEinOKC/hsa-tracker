/**
 * Household service — family group creation and management
 */

import api from './api'

export interface HouseholdOut {
  id: string
  name: string
  created_by_id: string
  created_at: string
}

export interface HouseholdRoleOut {
  id: string
  household_id: string
  name: string
  can_read_transactions: boolean
  can_write_transactions: boolean
  can_delete_transactions: boolean
  can_read_bank_accounts: boolean
  can_write_bank_accounts: boolean
  can_delete_bank_accounts: boolean
  can_read_documents: boolean
  can_write_documents: boolean
  can_delete_documents: boolean
  can_read_family_members: boolean
  can_write_family_members: boolean
  can_delete_family_members: boolean
  created_at: string
}

export interface HouseholdMemberOut {
  id: string
  household_id: string
  user_id: string
  username: string
  display_name: string
  role: HouseholdRoleOut
  is_admin: boolean
  joined_at: string
}

export interface HouseholdDetailOut {
  household: HouseholdOut
  roles: HouseholdRoleOut[]
  members: HouseholdMemberOut[]
}

export type HouseholdRoleCreate = Omit<HouseholdRoleOut, 'id' | 'household_id' | 'created_at'>
export type HouseholdRoleUpdate = Partial<HouseholdRoleCreate>

const householdsService = {
  async create(name: string): Promise<HouseholdDetailOut> {
    const r = await api.post<HouseholdDetailOut>('/households', { name })
    return r.data
  },

  async getMine(): Promise<HouseholdDetailOut> {
    const r = await api.get<HouseholdDetailOut>('/households/mine')
    return r.data
  },

  async createRole(data: HouseholdRoleCreate): Promise<HouseholdRoleOut> {
    const r = await api.post<HouseholdRoleOut>('/households/mine/roles', data)
    return r.data
  },

  async updateRole(roleId: string, data: HouseholdRoleUpdate): Promise<HouseholdRoleOut> {
    const r = await api.put<HouseholdRoleOut>(`/households/mine/roles/${roleId}`, data)
    return r.data
  },

  async deleteRole(roleId: string): Promise<void> {
    await api.delete(`/households/mine/roles/${roleId}`)
  },

  async removeMember(userId: string): Promise<void> {
    await api.delete(`/households/mine/members/${userId}`)
  },

  async transferAdmin(userId: string, stayAsRoleId?: string): Promise<HouseholdDetailOut> {
    const r = await api.post<HouseholdDetailOut>(
      `/households/mine/members/${userId}/transfer-admin`,
      { stay_as_role_id: stayAsRoleId || null }
    )
    return r.data
  },
}

export default householdsService
