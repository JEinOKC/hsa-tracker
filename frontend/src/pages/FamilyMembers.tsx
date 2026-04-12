import { useState, useEffect, useCallback } from 'react'
import { useToast } from '../components/Toast'
import { useSearchParams } from 'react-router-dom'
import { familyService, FamilyMember, EligibilityPeriod, FamilyMemberCreate } from '../services/family'
import familyInvitesService, { FamilyInvite } from '../services/familyInvites'
import householdsService, { HouseholdDetailOut, HouseholdMemberOut, HouseholdRoleOut, HouseholdRoleCreate as HHRoleCreate } from '../services/households'
import { useAuthStore } from '../store/authStore'

const RELATIONSHIPS = ['spouse', 'child', 'other'] as const

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  })
}

function EligibilityBadge({ periods }: { periods: EligibilityPeriod[] }) {
  const today = new Date().toISOString().split('T')[0]
  const active = periods.some(p => p.start_date <= today && (p.end_date === null || p.end_date >= today))
  return (
    <span className={`text-xs px-2 py-0.5 rounded font-medium ${active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
      {active ? 'HSA Eligible' : 'Not Eligible'}
    </span>
  )
}

interface AddMemberFormProps {
  onSave: (member: FamilyMember, invite?: FamilyInvite) => void
  onCancel: () => void
  household: HouseholdDetailOut | null
}

function AddMemberForm({ onSave, onCancel, household }: AddMemberFormProps) {
  const [form, setForm] = useState<FamilyMemberCreate>({
    name: '',
    member_relationship: 'spouse',
    date_of_birth: null,
    is_tax_dependent: false,
    eligibility_start: new Date().toISOString().split('T')[0],
    eligibility_end: null,
  })
  const [accountPath, setAccountPath] = useState<'none' | 'invite'>('none')
  const [inviteRoleId, setInviteRoleId] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const member = await familyService.create(form)
      if (accountPath === 'invite' && inviteRoleId) {
        const invite = await familyInvitesService.create(undefined, true, inviteRoleId, member.id)
        onSave(member, invite)
      } else {
        onSave(member)
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || 'Failed to save family member.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6 space-y-4">
      <h2 className="text-lg font-semibold text-gray-900">Add Family Member</h2>

      {error && <p className="text-sm text-red-600 bg-red-50 p-3 rounded">{error}</p>}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
          <input
            required
            type="text"
            value={form.name}
            onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
            placeholder="Full name"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Relationship *</label>
          <select
            value={form.member_relationship}
            onChange={e => setForm(f => ({ ...f, member_relationship: e.target.value }))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            {RELATIONSHIPS.map(r => (
              <option key={r} value={r} className="capitalize">{r.charAt(0).toUpperCase() + r.slice(1)}</option>
            ))}
          </select>
        </div>

        <div className="min-w-0">
          <label className="block text-sm font-medium text-gray-700 mb-1">Date of Birth</label>
          <input
            type="date"
            value={form.date_of_birth || ''}
            onChange={e => setForm(f => ({ ...f, date_of_birth: e.target.value || null }))}
            className="w-full max-w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
          />
        </div>

        <div className="flex items-center pt-6">
          <input
            type="checkbox"
            id="is_tax_dependent"
            checked={form.is_tax_dependent}
            onChange={e => setForm(f => ({ ...f, is_tax_dependent: e.target.checked }))}
            className="h-4 w-4 text-sky-600 rounded"
          />
          <label htmlFor="is_tax_dependent" className="ml-2 text-sm text-gray-700">
            Tax dependent (IRS)
          </label>
        </div>
      </div>

      <div className="border-t border-gray-100 pt-4">
        <p className="text-sm font-medium text-gray-700 mb-3">HSA Eligibility Period</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="min-w-0">
            <label className="block text-sm text-gray-600 mb-1">Start Date</label>
            <input
              type="date"
              value={form.eligibility_start || ''}
              onChange={e => setForm(f => ({ ...f, eligibility_start: e.target.value || null }))}
              className="w-full max-w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>
          <div className="min-w-0">
            <label className="block text-sm text-gray-600 mb-1">End Date <span className="text-gray-400">(leave blank if currently eligible)</span></label>
            <input
              type="date"
              value={form.eligibility_end || ''}
              onChange={e => setForm(f => ({ ...f, eligibility_end: e.target.value || null }))}
              className="w-full max-w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>
        </div>
      </div>

      {household && (
        <div className="border-t border-gray-100 pt-4 space-y-2">
          <p className="text-sm font-medium text-gray-700">Account access</p>
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="radio"
              name="accountPath"
              value="none"
              checked={accountPath === 'none'}
              onChange={() => setAccountPath('none')}
              className="mt-0.5"
            />
            <div>
              <span className="text-sm text-gray-800">No account needed</span>
              <p className="text-xs text-gray-400">Track their eligibility yourself — good for children and infants.</p>
            </div>
          </label>
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="radio"
              name="accountPath"
              value="invite"
              checked={accountPath === 'invite'}
              onChange={() => setAccountPath('invite')}
              className="mt-0.5"
            />
            <div className="flex-1">
              <span className="text-sm text-gray-800">Send an invite link</span>
              <p className="text-xs text-gray-400">They'll create their own login and manage their own data.</p>
              {accountPath === 'invite' && (
                <select
                  required
                  value={inviteRoleId}
                  onChange={e => setInviteRoleId(e.target.value)}
                  className="mt-2 w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
                >
                  <option value="">Select a household role…</option>
                  {household.roles.map(r => (
                    <option key={r.id} value={r.id}>{r.name}</option>
                  ))}
                </select>
              )}
            </div>
          </label>
        </div>
      )}

      <div className="flex justify-end gap-3">
        <button type="button" onClick={onCancel} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900">
          Cancel
        </button>
        <button
          type="submit"
          disabled={saving || (accountPath === 'invite' && !inviteRoleId)}
          className="px-5 py-2 text-sm bg-sky-600 hover:bg-sky-700 text-white rounded-lg disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Add Member'}
        </button>
      </div>
    </form>
  )
}

interface EligibilityManagerProps {
  member: FamilyMember
  onUpdated: (member: FamilyMember) => void
}

function EligibilityManager({ member, onUpdated }: EligibilityManagerProps) {
  const [adding, setAdding] = useState(false)
  const [newPeriod, setNewPeriod] = useState({ start_date: '', end_date: '', notes: '' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await familyService.addEligibility(member.id, {
        start_date: newPeriod.start_date,
        end_date: newPeriod.end_date || null,
        notes: newPeriod.notes || null,
      })
      const updated = await familyService.get(member.id)
      onUpdated(updated)
      setAdding(false)
      setNewPeriod({ start_date: '', end_date: '', notes: '' })
    } catch {
      setError('Failed to add eligibility period.')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (periodId: string) => {
    if (!confirm('Remove this eligibility period?')) return
    try {
      await familyService.deleteEligibility(member.id, periodId)
      const updated = await familyService.get(member.id)
      onUpdated(updated)
    } catch {
      setError('Failed to remove eligibility period.')
    }
  }

  return (
    <div className="mt-4 pl-4 border-l-2 border-gray-100">
      <div className="flex items-center justify-between mb-2">
        <p className="text-sm font-medium text-gray-600">HSA Eligibility Periods</p>
        <button
          onClick={() => setAdding(!adding)}
          className="text-xs text-sky-600 hover:text-sky-800"
        >
          + Add Period
        </button>
      </div>

      {error && <p className="text-xs text-red-600 mb-2">{error}</p>}

      {member.eligibility_periods.length === 0 && !adding && (
        <p className="text-xs text-gray-400">No eligibility periods defined. Add one to track HSA eligibility.</p>
      )}

      {member.eligibility_periods.map(period => (
        <div key={period.id} className="flex items-center justify-between text-sm py-1">
          <span className="text-gray-700">
            {formatDate(period.start_date)} → {period.end_date ? formatDate(period.end_date) : 'present'}
          </span>
          <button
            onClick={() => handleDelete(period.id)}
            className="text-xs text-red-400 hover:text-red-600 ml-4"
          >
            Remove
          </button>
        </div>
      ))}

      {adding && (
        <form onSubmit={handleAdd} className="mt-3 space-y-2 bg-gray-50 p-3 rounded-lg">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div className="min-w-0">
              <label className="block text-xs text-gray-500 mb-1">Start Date *</label>
              <input
                required
                type="date"
                value={newPeriod.start_date}
                onChange={e => setNewPeriod(p => ({ ...p, start_date: e.target.value }))}
                className="w-full max-w-full border border-gray-300 rounded px-2 py-1 text-sm"
              />
            </div>
            <div className="min-w-0">
              <label className="block text-xs text-gray-500 mb-1">End Date (blank = ongoing)</label>
              <input
                type="date"
                value={newPeriod.end_date}
                onChange={e => setNewPeriod(p => ({ ...p, end_date: e.target.value }))}
                className="w-full max-w-full border border-gray-300 rounded px-2 py-1 text-sm"
              />
            </div>
          </div>
          <input
            type="text"
            placeholder="Notes (optional)"
            value={newPeriod.notes}
            onChange={e => setNewPeriod(p => ({ ...p, notes: e.target.value }))}
            className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
          />
          <div className="flex gap-2 justify-end">
            <button type="button" onClick={() => setAdding(false)} className="text-xs text-gray-500">Cancel</button>
            <button
              type="submit"
              disabled={saving}
              className="text-xs bg-sky-600 text-white px-3 py-1 rounded disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}

interface MemberCardProps {
  member: FamilyMember
  currentUserId?: string
  viewerRelationship?: string
  householdMember?: HouseholdMemberOut
  householdRoles?: HouseholdRoleOut[]
  initialInvite?: FamilyInvite
  onUpdated: (member: FamilyMember) => void
  onDeactivated: (id: string) => void
  autoExpand?: boolean
}

function MemberCard({ member, currentUserId, viewerRelationship, householdMember, householdRoles, initialInvite, onUpdated, onDeactivated, autoExpand }: MemberCardProps) {
  const { toast } = useToast()
  const [expanded, setExpanded] = useState(autoExpand ?? false)
  const [pendingInvite, setPendingInvite] = useState<FamilyInvite | null>(initialInvite ?? null)
  const [showInviteForm, setShowInviteForm] = useState(false)
  const [inviteRoleId, setInviteRoleId] = useState('')
  const [inviting, setInviting] = useState(false)
  const [copied, setCopied] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editForm, setEditForm] = useState({ name: member.name, date_of_birth: member.date_of_birth || '', is_tax_dependent: member.is_tax_dependent })
  const [saving, setSaving] = useState(false)

  const isSelf = !!currentUserId && member.linked_user_id === currentUserId
  const canInvite = !householdMember && householdRoles && householdRoles.length > 0 && !isSelf

  const handleGenerateInvite = async (e: React.FormEvent) => {
    e.preventDefault()
    setInviting(true)
    try {
      const invite = await familyInvitesService.create(undefined, true, inviteRoleId, member.id)
      setPendingInvite(invite)
      setShowInviteForm(false)
    } catch {
      toast('Failed to generate invite link.', 'error')
    } finally {
      setInviting(false)
    }
  }

  const handleRevokeInvite = async () => {
    if (!pendingInvite || !confirm('Revoke this invite link?')) return
    try {
      await familyInvitesService.revoke(pendingInvite.token)
      setPendingInvite(null)
    } catch {
      toast('Failed to revoke invite.', 'error')
    }
  }

  const handleCopy = (url: string) => {
    navigator.clipboard.writeText(url)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleEditSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      const updated = await familyService.update(member.id, {
        name: editForm.name,
        date_of_birth: editForm.date_of_birth || null,
        is_tax_dependent: editForm.is_tax_dependent,
      })
      onUpdated(updated)
      setEditing(false)
    } catch {
      toast('Failed to save changes.', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleDeactivate = async () => {
    if (!confirm(`Remove ${member.name} from your family? Their expense history will be kept.`)) return
    try {
      await familyService.deactivate(member.id)
      onDeactivated(member.id)
    } catch {
      toast('Failed to remove family member.', 'error')
    }
  }

  return (
    <div className="bg-white rounded-lg shadow p-5">
      {/* Member info */}
      <div className="flex items-start gap-2 flex-wrap">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-semibold text-gray-900">{member.name}</h3>
            <span className="text-xs text-gray-500 capitalize bg-gray-100 px-2 py-0.5 rounded">
              {isSelf ? 'Self' : (member.member_relationship === 'self' && viewerRelationship) ? viewerRelationship : member.member_relationship}
            </span>
            {member.is_tax_dependent && (
              <span className="text-xs text-sky-600 bg-sky-50 px-2 py-0.5 rounded">Tax Dependent</span>
            )}
          </div>
          {householdMember && (
            <div className="flex items-center gap-2 mt-0.5 flex-wrap">
              <span className="text-xs text-gray-400">@{householdMember.username}</span>
              <span className="text-xs text-sky-600 bg-sky-50 px-1.5 py-0.5 rounded">
                {householdMember.is_admin && !householdMember.role.name.toLowerCase().includes('admin')
                  ? `${householdMember.role.name} (Admin)`
                  : householdMember.role.name}
              </span>
            </div>
          )}
          <div className="flex items-center gap-3 mt-1 flex-wrap">
            {member.date_of_birth && (
              <p className="text-sm text-gray-500">DOB: {formatDate(member.date_of_birth)}</p>
            )}
            <EligibilityBadge periods={member.eligibility_periods} />
          </div>
        </div>
      </div>
      {/* Action buttons — own row below info */}
      <div className="flex gap-3 items-center mt-3 pt-3 border-t border-gray-100 flex-wrap">
        {canInvite && !pendingInvite && !showInviteForm && (
          <button
            onClick={() => setShowInviteForm(true)}
            className="text-sm text-sky-600 hover:text-sky-800 border border-sky-200 px-2 py-0.5 rounded"
          >
            Invite to account
          </button>
        )}
        <button
          onClick={() => { setEditing(e => !e); setExpanded(false) }}
          className="text-sm text-sky-600 hover:text-sky-800"
        >
          {editing ? 'Cancel' : 'Edit'}
        </button>
        {!editing && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-sm text-sky-600 hover:text-sky-800"
          >
            {expanded ? 'Hide Eligibility' : 'Eligibility'}
          </button>
        )}
        <button
          onClick={handleDeactivate}
          className="text-sm text-red-400 hover:text-red-600 ml-auto"
        >
          Remove
        </button>
      </div>

      {editing && (
        <form onSubmit={handleEditSave} className="mt-3 bg-gray-50 rounded-lg p-3 space-y-2">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Name</label>
            <input
              required
              value={editForm.name}
              onChange={e => setEditForm(f => ({ ...f, name: e.target.value }))}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Date of Birth</label>
            <input
              type="date"
              value={editForm.date_of_birth}
              onChange={e => setEditForm(f => ({ ...f, date_of_birth: e.target.value }))}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={editForm.is_tax_dependent}
              onChange={e => setEditForm(f => ({ ...f, is_tax_dependent: e.target.checked }))}
            />
            Tax dependent
          </label>
          <div className="flex gap-2 justify-end">
            <button type="button" onClick={() => setEditing(false)} className="text-sm text-gray-500">Cancel</button>
            <button type="submit" disabled={saving} className="text-sm bg-sky-600 hover:bg-sky-700 text-white px-3 py-1.5 rounded-lg disabled:opacity-50">
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>
      )}

      {showInviteForm && householdRoles && (
        <form onSubmit={handleGenerateInvite} className="mt-3 bg-gray-50 rounded-lg p-3 space-y-2">
          <select
            required
            value={inviteRoleId}
            onChange={e => setInviteRoleId(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            <option value="">Select a household role…</option>
            {householdRoles.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
          </select>
          <div className="flex gap-2 justify-end">
            <button type="button" onClick={() => setShowInviteForm(false)} className="text-sm text-gray-500">Cancel</button>
            <button type="submit" disabled={inviting || !inviteRoleId} className="text-sm bg-sky-600 hover:bg-sky-700 text-white px-3 py-1.5 rounded-lg disabled:opacity-50">
              {inviting ? 'Generating…' : 'Generate Invite'}
            </button>
          </div>
        </form>
      )}

      {pendingInvite && (
        <div className="mt-3 border border-sky-200 bg-sky-50 rounded-xl overflow-hidden">
          <div className="px-4 pt-4 pb-3 flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-sky-900">Invite ready for {member.name}</p>
              <p className="text-xs text-sky-600 mt-0.5">Single-use · expires in 72h · they'll also need your Family PIN</p>
            </div>
            <button onClick={handleRevokeInvite} className="text-xs text-red-400 hover:text-red-600 shrink-0 ml-3">Revoke</button>
          </div>

          {pendingInvite.qr_code_data_url && (
            <div className="flex justify-center bg-white border-y border-sky-100 py-5">
              <img
                src={pendingInvite.qr_code_data_url}
                alt="QR code for invite link"
                className="w-40 h-40 rounded-lg shadow-sm"
              />
            </div>
          )}

          <div className="px-4 py-3 flex items-center gap-2">
            <input
              readOnly
              value={pendingInvite.invite_url}
              className="flex-1 font-mono text-xs bg-white border border-sky-200 rounded-lg px-2.5 py-2 text-gray-600 min-w-0"
            />
            <button
              onClick={() => handleCopy(pendingInvite.invite_url)}
              className="text-xs bg-sky-600 hover:bg-sky-700 text-white px-3 py-2 rounded-lg shrink-0 font-medium transition-colors"
            >
              {copied ? 'Copied!' : 'Copy link'}
            </button>
          </div>
        </div>
      )}

      {expanded && (
        <EligibilityManager member={member} onUpdated={onUpdated} />
      )}
    </div>
  )
}


function ActiveInvitesList() {
  const { toast } = useToast()
  const [invites, setInvites] = useState<FamilyInvite[]>([])

  useEffect(() => {
    familyInvitesService.list().then(setInvites).catch(() => {})
  }, [])

  const handleRevoke = async (token: string) => {
    if (!confirm('Revoke this invite link? It will no longer work.')) return
    try {
      await familyInvitesService.revoke(token)
      setInvites(prev => prev.filter(i => i.token !== token))
    } catch {
      toast('Failed to revoke invite.', 'error')
    }
  }

  const formatExpiry = (expiresAt: string) => {
    const diff = new Date(expiresAt).getTime() - Date.now()
    const hours = Math.floor(diff / 3600000)
    if (hours < 1) return 'expires soon'
    if (hours < 24) return `expires in ${hours}h`
    return `expires in ${Math.floor(hours / 24)}d`
  }

  if (invites.length === 0) return null

  return (
    <div className="border-t border-gray-100 pt-4 space-y-2">
      <p className="text-sm font-medium text-gray-700">Active Invites</p>
      {invites.map(invite => (
        <div key={invite.token} className="flex items-center justify-between text-sm bg-gray-50 rounded-lg px-3 py-2 gap-2">
          <div className="min-w-0">
            <span className="font-mono text-gray-700 truncate block">{invite.token}</span>
            <span className="text-xs text-gray-400">
              {invite.label ? `${invite.label} · ` : ''}{formatExpiry(invite.expires_at)}
            </span>
          </div>
          <button onClick={() => handleRevoke(invite.token)} className="text-xs text-red-400 hover:text-red-600 shrink-0">Revoke</button>
        </div>
      ))}
    </div>
  )
}

const HH_DEFAULT_ROLE: HHRoleCreate = {
  name: '',
  can_read_transactions: true,  can_write_transactions: false,  can_delete_transactions: false,
  can_read_bank_accounts: true, can_write_bank_accounts: false, can_delete_bank_accounts: false,
  can_read_documents: true,     can_write_documents: false,     can_delete_documents: false,
  can_read_family_members: true, can_write_family_members: false, can_delete_family_members: false,
}
const HH_RESOURCES = ['transactions', 'bank_accounts', 'documents', 'family_members'] as const
const HH_RESOURCE_LABELS: Record<string, string> = {
  transactions: 'Transactions', bank_accounts: 'Bank Accounts', documents: 'Documents', family_members: 'Family Members',
}

function HHRoleForm({ onSave, onCancel, existing }: { onSave: (r: HouseholdRoleOut) => void; onCancel: () => void; existing?: HouseholdRoleOut }) {
  const [form, setForm] = useState<HHRoleCreate>(existing ? {
    name: existing.name,
    can_read_transactions: existing.can_read_transactions,
    can_write_transactions: existing.can_write_transactions,
    can_delete_transactions: existing.can_delete_transactions,
    can_read_bank_accounts: existing.can_read_bank_accounts,
    can_write_bank_accounts: existing.can_write_bank_accounts,
    can_delete_bank_accounts: existing.can_delete_bank_accounts,
    can_read_documents: existing.can_read_documents,
    can_write_documents: existing.can_write_documents,
    can_delete_documents: existing.can_delete_documents,
    can_read_family_members: existing.can_read_family_members,
    can_write_family_members: existing.can_write_family_members,
    can_delete_family_members: existing.can_delete_family_members,
  } : { ...HH_DEFAULT_ROLE })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const toggle = (key: keyof HHRoleCreate) => setForm(f => ({ ...f, [key]: !f[key] }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const saved = existing
        ? await householdsService.updateRole(existing.id, form)
        : await householdsService.createRole(form)
      onSave(saved)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to save role.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-gray-50 rounded-lg p-4 space-y-4">
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Role name *</label>
        <input
          required
          type="text"
          value={form.name}
          onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
          placeholder="e.g. Spouse, Child, Read Only"
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
        />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className="text-left text-gray-500 font-normal pb-2 pr-4">Resource</th>
              <th className="text-center text-gray-500 font-normal pb-2 px-2">Read</th>
              <th className="text-center text-gray-500 font-normal pb-2 px-2">Write</th>
              <th className="text-center text-gray-500 font-normal pb-2 px-2">Delete</th>
            </tr>
          </thead>
          <tbody>
            {HH_RESOURCES.map(res => (
              <tr key={res} className="border-t border-gray-100">
                <td className="py-2 pr-4 text-gray-700">{HH_RESOURCE_LABELS[res]}</td>
                {(['read', 'write', 'delete'] as const).map(op => {
                  const key = `can_${op}_${res}` as keyof HHRoleCreate
                  return (
                    <td key={op} className="py-2 px-2 text-center">
                      <input type="checkbox" checked={form[key] as boolean} onChange={() => toggle(key)} className="h-4 w-4 text-sky-600 rounded" />
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex justify-end gap-3">
        <button type="button" onClick={onCancel} className="text-sm text-gray-500 hover:text-gray-700">Cancel</button>
        <button type="submit" disabled={saving} className="text-sm bg-sky-600 hover:bg-sky-700 text-white px-4 py-2 rounded-lg disabled:opacity-50">
          {saving ? 'Saving…' : existing ? 'Save Changes' : 'Create Role'}
        </button>
      </div>
    </form>
  )
}

function HouseholdSection({
  household,
  onHouseholdChange,
}: {
  household: HouseholdDetailOut
  onHouseholdChange: (detail: HouseholdDetailOut) => void
}) {
  const { toast } = useToast()
  const [showRoleForm, setShowRoleForm] = useState(false)
  const [editingRole, setEditingRole] = useState<HouseholdRoleOut | null>(null)
  const [pin, setPin] = useState<string | null>(null)
  const [resetting, setResetting] = useState(false)

  useEffect(() => {
    familyInvitesService.getFamilyPin().then(setPin).catch(() => {})
  }, [])

  const refresh = async () => {
    const d = await householdsService.getMine().catch(() => null)
    if (d) onHouseholdChange(d)
  }

  const handleRoleSaved = (role: HouseholdRoleOut) => {
    setShowRoleForm(false)
    setEditingRole(null)
    const roles = household.roles.some(r => r.id === role.id)
      ? household.roles.map(r => r.id === role.id ? role : r)
      : [...household.roles, role]
    onHouseholdChange({ ...household, roles })
    refresh()
  }

  const handleDeleteRole = async (roleId: string) => {
    if (!confirm('Delete this role? Members using it must be reassigned first.')) return
    try {
      await householdsService.deleteRole(roleId)
      onHouseholdChange({ ...household, roles: household.roles.filter(r => r.id !== roleId) })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast(msg || 'Failed to delete role.', 'error')
    }
  }

  const handleResetPin = async () => {
    if (!confirm('Generate a new family PIN? Your old PIN will stop working immediately.')) return
    setResetting(true)
    try {
      const newPin = await familyInvitesService.resetFamilyPin()
      setPin(newPin)
    } finally {
      setResetting(false)
    }
  }

  return (
    <div className="bg-white rounded-lg shadow p-5 space-y-5">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-3">Household Settings</p>

        {/* Roles */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-gray-700">Roles</p>
            {!showRoleForm && (
              <button onClick={() => setShowRoleForm(true)} className="text-xs text-sky-600 hover:text-sky-800">+ New Role</button>
            )}
          </div>
          {showRoleForm && (
            <div className="mb-3">
              <HHRoleForm onSave={handleRoleSaved} onCancel={() => setShowRoleForm(false)} />
            </div>
          )}
          <div className="space-y-2">
            {household.roles.map(role => {
              const usedByAdmin = household.members.some(m => m.is_admin && m.role.id === role.id)
              if (editingRole?.id === role.id) {
                return (
                  <div key={role.id} className="mb-3">
                    <HHRoleForm existing={role} onSave={handleRoleSaved} onCancel={() => setEditingRole(null)} />
                  </div>
                )
              }
              return (
                <div key={role.id} className="flex items-start justify-between bg-gray-50 rounded-lg px-3 py-2 gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium text-gray-800">{role.name}</span>
                      {usedByAdmin && <span className="text-xs text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded">Admin role</span>}
                    </div>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {HH_RESOURCES.filter(r => role[`can_read_${r}` as keyof HouseholdRoleOut]).map(r => HH_RESOURCE_LABELS[r]).join(', ') || 'No read access'}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <button onClick={() => setEditingRole(role)} className="text-xs text-sky-500 hover:text-sky-700">Edit</button>
                    {!usedByAdmin && (
                      <button onClick={() => handleDeleteRole(role.id)} className="text-xs text-red-400 hover:text-red-600">Delete</button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Family PIN */}
      <div className="border-t border-gray-100 pt-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-gray-700 mb-1">Family PIN</p>
          <p className="text-xs text-gray-400 mb-2">Each account has its own PIN. When you send an invite with PIN protection, the recipient needs <em>your</em> PIN to accept it.</p>
          {pin ? (
            <div className="inline-flex items-center gap-3 bg-gray-50 border border-gray-200 rounded-lg px-3 py-1.5">
              <span className="font-mono font-semibold text-gray-800 tracking-wide">{pin}</span>
              <button onClick={() => navigator.clipboard.writeText(pin)} className="text-xs text-sky-600 hover:text-sky-800">Copy</button>
            </div>
          ) : (
            <p className="text-xs text-gray-400 italic">Loading…</p>
          )}
        </div>
        <button onClick={handleResetPin} disabled={resetting} className="text-xs text-gray-500 hover:text-red-600 disabled:opacity-50 ml-4 shrink-0">
          {resetting ? 'Resetting…' : 'Reset PIN'}
        </button>
      </div>

      <ActiveInvitesList />
    </div>
  )
}



export default function FamilyMembers() {
  const { user: currentUser } = useAuthStore()
  const [members, setMembers] = useState<FamilyMember[]>([])
  const [loading, setLoading] = useState(true)
  const [showAddForm, setShowAddForm] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [household, setHousehold] = useState<HouseholdDetailOut | null>(null)
  const [householdLoading, setHouseholdLoading] = useState(true)
  const [pendingInvites, setPendingInvites] = useState<Record<string, FamilyInvite>>({})
  const [searchParams, setSearchParams] = useSearchParams()
  const isSetup = searchParams.get('setup') === '1'

  const loadMembers = useCallback(async () => {
    try {
      const data = await familyService.list()
      setMembers(data)
    } catch {
      setError('Failed to load family members.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadMembers()
    householdsService.getMine()
      .then(d => setHousehold(d))
      .catch(() => setHousehold(null))
      .finally(() => setHouseholdLoading(false))
  }, [loadMembers])

  // Poll every 10 s while there are pending invites; clear them once the invite is accepted
  useEffect(() => {
    if (Object.keys(pendingInvites).length === 0) return
    const id = setInterval(async () => {
      const [freshMembers, freshHousehold] = await Promise.allSettled([
        familyService.list(),
        householdsService.getMine(),
      ])
      if (freshMembers.status === 'fulfilled') {
        setMembers(freshMembers.value)
        setPendingInvites(prev => {
          const next = { ...prev }
          for (const memberId of Object.keys(prev)) {
            const fm = freshMembers.value.find(m => m.id === memberId)
            if (fm?.linked_user_id) delete next[memberId]
          }
          return next
        })
      }
      if (freshHousehold.status === 'fulfilled') setHousehold(freshHousehold.value)
    }, 10_000)
    return () => clearInterval(id)
  }, [pendingInvites])

  const handleSaved = (member: FamilyMember, invite?: FamilyInvite) => {
    setMembers(prev => [...prev, member])
    if (invite) setPendingInvites(prev => ({ ...prev, [member.id]: invite }))
    setShowAddForm(false)
  }

  const handleUpdated = (updated: FamilyMember) => {
    setMembers(prev => prev.map(m => m.id === updated.id ? updated : m))
  }

  const handleDeactivated = (id: string) => {
    setMembers(prev => prev.filter(m => m.id !== id))
  }

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <p className="text-gray-500">Loading family members…</p>
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-3xl">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Family Members</h1>
          {!householdLoading && household && (
            <p className="text-gray-500 mt-1">{household.household.name}</p>
          )}
        </div>
        {!showAddForm && (
          <button
            onClick={() => setShowAddForm(true)}
            className="text-sm bg-sky-600 hover:bg-sky-700 text-white font-medium px-4 py-2 rounded-lg shrink-0"
          >
            + Add Member
          </button>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 text-red-700 text-sm">
          {error}
        </div>
      )}

      {isSetup && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-6 text-sm text-green-800">
          <strong>Welcome!</strong> Your account has been created. Set your HSA coverage dates below — this tells the app when you were eligible.
          <button onClick={() => setSearchParams({})} className="ml-3 text-green-600 underline hover:text-green-800">Dismiss</button>
        </div>
      )}

      {showAddForm && (
        <div className="mb-4">
          <AddMemberForm
            household={household}
            onSave={handleSaved}
            onCancel={() => setShowAddForm(false)}
          />
        </div>
      )}

      {members.length === 0 && !showAddForm ? (
        <div className="bg-white rounded-lg shadow p-10 text-center text-gray-400">
          <p className="text-base mb-1">No members tracked yet.</p>
          <p className="text-sm">Your own eligibility card will appear here after registration.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {members.map(member => (
            <MemberCard
              key={member.id}
              member={member}
              currentUserId={currentUser?.id}
              viewerRelationship={members.find(m => m.linked_user_id === currentUser?.id)?.member_relationship}
              householdMember={household?.members.find(m => m.user_id === member.linked_user_id)}
              householdRoles={household?.roles}
              initialInvite={pendingInvites[member.id]}
              onUpdated={handleUpdated}
              onDeactivated={handleDeactivated}
              autoExpand={isSetup && (member.member_relationship === 'self' || member.linked_user_id === currentUser?.id)}
            />
          ))}
        </div>
      )}

      {!householdLoading && household && (
        <div className="mt-6">
          <HouseholdSection household={household} onHouseholdChange={setHousehold} />
        </div>
      )}
    </div>
  )
}
