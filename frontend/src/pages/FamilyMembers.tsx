import { useState, useEffect, useCallback } from 'react'
import { familyService, FamilyMember, EligibilityPeriod, FamilyMemberCreate } from '../services/family'

const RELATIONSHIPS = ['self', 'spouse', 'child', 'other'] as const

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
  onSave: (member: FamilyMember) => void
  onCancel: () => void
}

function AddMemberForm({ onSave, onCancel }: AddMemberFormProps) {
  const [form, setForm] = useState<FamilyMemberCreate>({
    name: '',
    member_relationship: 'self',
    date_of_birth: null,
    is_tax_dependent: false,
    eligibility_start: new Date().toISOString().split('T')[0],
    eligibility_end: null,
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const member = await familyService.create(form)
      onSave(member)
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
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Full name"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Relationship *</label>
          <select
            value={form.member_relationship}
            onChange={e => setForm(f => ({ ...f, member_relationship: e.target.value }))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {RELATIONSHIPS.map(r => (
              <option key={r} value={r} className="capitalize">{r.charAt(0).toUpperCase() + r.slice(1)}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Date of Birth</label>
          <input
            type="date"
            value={form.date_of_birth || ''}
            onChange={e => setForm(f => ({ ...f, date_of_birth: e.target.value || null }))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="flex items-center pt-6">
          <input
            type="checkbox"
            id="is_tax_dependent"
            checked={form.is_tax_dependent}
            onChange={e => setForm(f => ({ ...f, is_tax_dependent: e.target.checked }))}
            className="h-4 w-4 text-blue-600 rounded"
          />
          <label htmlFor="is_tax_dependent" className="ml-2 text-sm text-gray-700">
            Tax dependent (IRS)
          </label>
        </div>
      </div>

      <div className="border-t border-gray-100 pt-4">
        <p className="text-sm font-medium text-gray-700 mb-3">HSA Eligibility Period</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-gray-600 mb-1">Start Date</label>
            <input
              type="date"
              value={form.eligibility_start || ''}
              onChange={e => setForm(f => ({ ...f, eligibility_start: e.target.value || null }))}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">End Date <span className="text-gray-400">(leave blank if currently eligible)</span></label>
            <input
              type="date"
              value={form.eligibility_end || ''}
              onChange={e => setForm(f => ({ ...f, eligibility_end: e.target.value || null }))}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      <div className="flex justify-end gap-3">
        <button type="button" onClick={onCancel} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900">
          Cancel
        </button>
        <button
          type="submit"
          disabled={saving}
          className="px-5 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50"
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
          className="text-xs text-blue-600 hover:text-blue-800"
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
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Start Date *</label>
              <input
                required
                type="date"
                value={newPeriod.start_date}
                onChange={e => setNewPeriod(p => ({ ...p, start_date: e.target.value }))}
                className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">End Date (blank = ongoing)</label>
              <input
                type="date"
                value={newPeriod.end_date}
                onChange={e => setNewPeriod(p => ({ ...p, end_date: e.target.value }))}
                className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
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
              className="text-xs bg-blue-600 text-white px-3 py-1 rounded disabled:opacity-50"
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
  onUpdated: (member: FamilyMember) => void
  onDeactivated: (id: string) => void
}

function MemberCard({ member, onUpdated, onDeactivated }: MemberCardProps) {
  const [expanded, setExpanded] = useState(false)

  const handleDeactivate = async () => {
    if (!confirm(`Remove ${member.name} from your family? Their expense history will be kept.`)) return
    try {
      await familyService.deactivate(member.id)
      onDeactivated(member.id)
    } catch {
      alert('Failed to remove family member.')
    }
  }

  return (
    <div className="bg-white rounded-lg shadow p-5">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-gray-900">{member.name}</h3>
            <span className="text-xs text-gray-500 capitalize bg-gray-100 px-2 py-0.5 rounded">
              {member.member_relationship}
            </span>
            {member.is_tax_dependent && (
              <span className="text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded">Tax Dependent</span>
            )}
          </div>
          <div className="flex items-center gap-3 mt-1">
            {member.date_of_birth && (
              <p className="text-sm text-gray-500">DOB: {formatDate(member.date_of_birth)}</p>
            )}
            <EligibilityBadge periods={member.eligibility_periods} />
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            {expanded ? 'Hide' : 'Eligibility'}
          </button>
          <button
            onClick={handleDeactivate}
            className="text-sm text-red-400 hover:text-red-600"
          >
            Remove
          </button>
        </div>
      </div>

      {expanded && (
        <EligibilityManager member={member} onUpdated={onUpdated} />
      )}
    </div>
  )
}

export default function FamilyMembers() {
  const [members, setMembers] = useState<FamilyMember[]>([])
  const [loading, setLoading] = useState(true)
  const [showAddForm, setShowAddForm] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
  }, [loadMembers])

  const handleSaved = (member: FamilyMember) => {
    setMembers(prev => [...prev, member])
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
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Family Members</h1>
          <p className="text-gray-500 mt-1">Track who is HSA-eligible and tag spending by person.</p>
        </div>
        {!showAddForm && (
          <button
            onClick={() => setShowAddForm(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white font-medium px-5 py-2 rounded-lg"
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

      {showAddForm && (
        <div className="mb-6">
          <AddMemberForm onSave={handleSaved} onCancel={() => setShowAddForm(false)} />
        </div>
      )}

      <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 mb-6 text-sm text-blue-800">
        <strong>About eligibility periods:</strong> Each family member can have one or more date ranges when they were covered by an HDHP and HSA-eligible. When you tag a transaction to a family member, we'll automatically warn you if they weren't eligible on that date.
      </div>

      {members.length === 0 && !showAddForm ? (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <p className="text-gray-400 text-lg mb-2">No family members yet.</p>
          <p className="text-gray-400 text-sm">Add yourself first, then your spouse and dependents.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {members.map(member => (
            <MemberCard
              key={member.id}
              member={member}
              onUpdated={handleUpdated}
              onDeactivated={handleDeactivated}
            />
          ))}
        </div>
      )}
    </div>
  )
}
