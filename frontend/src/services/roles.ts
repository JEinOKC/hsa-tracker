import api from './api'

export interface AccountRole {
  id: string
  owner_user_id: string
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

export type AccountRoleCreate = Omit<AccountRole, 'id' | 'owner_user_id' | 'created_at'>

export interface AccessGrant {
  id: string
  sub_user_id: string
  sub_username: string
  sub_display_name: string
  role: AccountRole
  granted_at: string
}

export interface MyAccess {
  owner_user_id: string
  owner_username: string
  owner_display_name: string
  role: AccountRole
  granted_at: string
}

const rolesService = {
  async listRoles(): Promise<AccountRole[]> {
    const r = await api.get<AccountRole[]>('/roles')
    return r.data
  },

  async createRole(data: AccountRoleCreate): Promise<AccountRole> {
    const r = await api.post<AccountRole>('/roles', data)
    return r.data
  },

  async updateRole(id: string, data: AccountRoleCreate): Promise<AccountRole> {
    const r = await api.put<AccountRole>(`/roles/${id}`, data)
    return r.data
  },

  async deleteRole(id: string): Promise<void> {
    await api.delete(`/roles/${id}`)
  },

  async listAccess(): Promise<AccessGrant[]> {
    const r = await api.get<AccessGrant[]>('/roles/access')
    return r.data
  },

  async grantAccess(username: string, roleId: string): Promise<AccessGrant> {
    const r = await api.post<AccessGrant>('/roles/access', { username, role_id: roleId })
    return r.data
  },

  async revokeAccess(subUserId: string): Promise<void> {
    await api.delete(`/roles/access/${subUserId}`)
  },

  async listMyAccess(): Promise<MyAccess[]> {
    const r = await api.get<MyAccess[]>('/roles/my-access')
    return r.data
  },
}

export default rolesService
