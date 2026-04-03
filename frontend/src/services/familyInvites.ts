/**
 * Family invite link service — in-app invite generation and validation
 */

import api from './api'

export interface FamilyInvite {
  token: string
  label: string | null
  invite_url: string
  qr_code_data_url: string
  expires_at: string
  require_pin: boolean
  is_used: boolean
}

export interface ValidateInviteResponse {
  valid: boolean
  require_pin: boolean
  expires_at: string | null
  family_member_name?: string | null
}

export interface FamilyPinResponse {
  pin: string
}

const familyInvitesService = {
  async create(label?: string, requirePin = true, householdRoleId?: string, familyMemberId?: string): Promise<FamilyInvite> {
    const response = await api.post<FamilyInvite>('/family-invites', {
      label: label || null,
      require_pin: requirePin,
      household_role_id: householdRoleId || null,
      family_member_id: familyMemberId || null,
    })
    return response.data
  },

  async list(): Promise<FamilyInvite[]> {
    const response = await api.get<FamilyInvite[]>('/family-invites')
    return response.data
  },

  async revoke(token: string): Promise<void> {
    await api.delete(`/family-invites/${token}`)
  },

  async validate(token: string): Promise<ValidateInviteResponse> {
    const response = await api.get<ValidateInviteResponse>(`/family-invites/validate/${token}`)
    return response.data
  },

  async getFamilyPin(): Promise<string> {
    const response = await api.get<FamilyPinResponse>('/auth/family-pin')
    return response.data.pin
  },

  async resetFamilyPin(): Promise<string> {
    const response = await api.post<FamilyPinResponse>('/auth/family-pin/reset')
    return response.data.pin
  },
}

export default familyInvitesService
