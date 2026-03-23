import { useState, useEffect, useCallback } from 'react'
import { bankService, BankTransaction, HSA_CATEGORIES } from '../services/bank'
import { familyService, FamilyMember } from '../services/family'

function formatAmount(amount: string): string {
  const n = parseFloat(amount)
  const abs = Math.abs(n).toFixed(2)
  return n < 0 ? `-$${abs}` : `+$${abs}`
}

function formatDate(dateStr: string): string {
  return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  })
}

// ─── Inline HSA toggle ───────────────────────────────────────────────────────

interface HsaToggleProps {
  txn: BankTransaction
  onChange: (updated: BankTransaction) => void
}

function HsaToggle({ txn, onChange }: HsaToggleProps) {
  const [saving, setSaving] = useState(false)

  const toggle = async () => {
    // cycle: null → true → false → null
    const next =
      txn.is_hsa_eligible === null ? true :
      txn.is_hsa_eligible === true ? false : null

    setSaving(true)
    try {
      const updated = await bankService.annotateTransaction(txn.id, { is_hsa_eligible: next })
      onChange(updated)
    } finally {
      setSaving(false)
    }
  }

  if (saving) return <span className="text-xs text-gray-400 w-16 inline-block text-center">…</span>

  if (txn.is_hsa_eligible === true)
    return (
      <button onClick={toggle} className="text-xs font-medium px-2 py-0.5 rounded bg-green-100 text-green-700 hover:bg-green-200 w-16">
        HSA
      </button>
    )
  if (txn.is_hsa_eligible === false)
    return (
      <button onClick={toggle} className="text-xs font-medium px-2 py-0.5 rounded bg-red-50 text-red-500 hover:bg-red-100 w-16">
        Not HSA
      </button>
    )
  return (
    <button onClick={toggle} className="text-xs font-medium px-2 py-0.5 rounded bg-gray-100 text-gray-400 hover:bg-gray-200 w-16">
      Mark
    </button>
  )
}

// ─── Inline member picker ─────────────────────────────────────────────────────

interface MemberPickerProps {
  txn: BankTransaction
  members: FamilyMember[]
  onChange: (updated: BankTransaction) => void
}

function MemberPicker({ txn, members, onChange }: MemberPickerProps) {
  const [saving, setSaving] = useState(false)

  const handleChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value || null
    setSaving(true)
    try {
      const updated = await bankService.annotateTransaction(txn.id, { family_member_id: value })
      onChange(updated)
    } finally {
      setSaving(false)
    }
  }

  return (
    <select
      value={txn.family_member_id ?? ''}
      onChange={handleChange}
      disabled={saving}
      className="text-xs border border-gray-200 rounded px-1 py-0.5 text-gray-600 bg-white disabled:opacity-50 max-w-[110px]"
    >
      <option value="">— person —</option>
      {members.map(m => (
        <option key={m.id} value={m.id}>{m.name}</option>
      ))}
    </select>
  )
}

// ─── Inline category picker (only shown on HSA tab) ──────────────────────────

interface CategoryPickerProps {
  txn: BankTransaction
  onChange: (updated: BankTransaction) => void
}

function CategoryPicker({ txn, onChange }: CategoryPickerProps) {
  const [saving, setSaving] = useState(false)

  const handleChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value || null
    setSaving(true)
    try {
      const updated = await bankService.annotateTransaction(txn.id, { hsa_category: value })
      onChange(updated)
    } finally {
      setSaving(false)
    }
  }

  return (
    <select
      value={txn.hsa_category ?? ''}
      onChange={handleChange}
      disabled={saving}
      className="text-xs border border-gray-200 rounded px-1 py-0.5 text-gray-600 bg-white disabled:opacity-50 max-w-[130px]"
    >
      <option value="">— category —</option>
      {HSA_CATEGORIES.map(c => (
        <option key={c.value} value={c.value}>{c.label}</option>
      ))}
    </select>
  )
}

// ─── Transaction row ──────────────────────────────────────────────────────────

interface TxnRowProps {
  txn: BankTransaction
  members: FamilyMember[]
  showCategory: boolean
  onChange: (updated: BankTransaction) => void
}

function TxnRow({ txn, members, showCategory, onChange }: TxnRowProps) {
  const amount = parseFloat(txn.amount)
  return (
    <div className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 border-b border-gray-50 last:border-0">
      {/* Date */}
      <span className="text-xs text-gray-400 w-24 shrink-0">{formatDate(txn.transaction_date)}</span>

      {/* Description + account */}
      <div className="flex-1 min-w-0">
        <p className="text-sm text-gray-900 truncate">{txn.description || '(no description)'}</p>
        <p className="text-xs text-gray-400 truncate">
          {txn.institution_name || txn.account_name || ''}
          {txn.account_name && txn.institution_name ? ` · ${txn.account_name}` : ''}
        </p>
      </div>

      {/* Amount */}
      <span className={`text-sm font-semibold w-20 text-right shrink-0 ${amount < 0 ? 'text-gray-900' : 'text-green-600'}`}>
        {formatAmount(txn.amount)}
      </span>

      {/* HSA toggle */}
      <div className="shrink-0">
        <HsaToggle txn={txn} onChange={onChange} />
      </div>

      {/* Person picker */}
      <div className="shrink-0">
        <MemberPicker txn={txn} members={members} onChange={onChange} />
      </div>

      {/* Category (HSA tab only) */}
      {showCategory && (
        <div className="shrink-0">
          <CategoryPicker txn={txn} onChange={onChange} />
        </div>
      )}
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

type Tab = 'all' | 'hsa'

export default function Transactions() {
  const [tab, setTab] = useState<Tab>('all')
  const [transactions, setTransactions] = useState<BankTransaction[]>([])
  const [members, setMembers] = useState<FamilyMember[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  // Filters
  const [search, setSearch] = useState('')
  const [filterMember, setFilterMember] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  const load = useCallback(async (activeTab: Tab) => {
    setLoading(true)
    setError(null)
    try {
      const [txns, fam] = await Promise.all([
        bankService.listAllTransactions({
          is_hsa_eligible: activeTab === 'hsa' ? true : undefined,
          limit: 500,
        }),
        familyService.list(),
      ])
      setTransactions(txns)
      setMembers(fam)
    } catch {
      setError('Failed to load transactions.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load(tab) }, [tab, load])

  const handleChange = useCallback((updated: BankTransaction) => {
    setTransactions(prev => prev.map(t => t.id === updated.id ? updated : t))
  }, [])

  const switchTab = (next: Tab) => {
    setTab(next)
    setSearch('')
    setFilterMember('')
  }

  // Client-side filter on top of server results
  const visible = transactions.filter(t => {
    if (search && !t.description?.toLowerCase().includes(search.toLowerCase())) return false
    if (filterMember && t.family_member_id !== filterMember) return false
    if (startDate && t.transaction_date < startDate) return false
    if (endDate && t.transaction_date > endDate) return false
    return true
  })

  const hsaTotal = tab === 'hsa'
    ? visible.reduce((sum, t) => sum + parseFloat(t.amount), 0)
    : null

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Transactions</h1>
          <p className="text-gray-500 mt-1">Review and tag transactions as HSA-eligible.</p>
        </div>
        {hsaTotal !== null && (
          <div className="text-right">
            <p className="text-xs text-gray-400">HSA total</p>
            <p className="text-xl font-bold text-green-700">{formatAmount(hsaTotal.toFixed(2))}</p>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-gray-200">
        {(['all', 'hsa'] as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => switchTab(t)}
            className={`px-5 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {t === 'all' ? 'All Transactions' : 'HSA Transactions'}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 mb-4">
        <input
          type="text"
          placeholder="Search description…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-52 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <select
          value={filterMember}
          onChange={e => setFilterMember(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All people</option>
          {members.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
        </select>
        <input
          type="date"
          value={startDate}
          onChange={e => setStartDate(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <span className="self-center text-gray-400 text-sm">to</span>
        <input
          type="date"
          value={endDate}
          onChange={e => setEndDate(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        {(search || filterMember || startDate || endDate) && (
          <button
            onClick={() => { setSearch(''); setFilterMember(''); setStartDate(''); setEndDate('') }}
            className="text-xs text-gray-400 hover:text-gray-600 px-2"
          >
            Clear
          </button>
        )}
      </div>

      {/* Column headers */}
      <div className="flex items-center gap-3 px-4 py-2 text-xs font-medium text-gray-400 uppercase tracking-wide">
        <span className="w-24 shrink-0">Date</span>
        <span className="flex-1">Description</span>
        <span className="w-20 text-right shrink-0">Amount</span>
        <span className="w-16 shrink-0">HSA?</span>
        <span className="w-[110px] shrink-0">Person</span>
        {tab === 'hsa' && <span className="w-[130px] shrink-0">Category</span>}
      </div>

      {/* Body */}
      <div className="bg-white rounded-lg shadow">
        {error && (
          <div className="p-6 text-red-600 text-sm">{error}</div>
        )}
        {loading ? (
          <div className="p-12 text-center text-gray-400">Loading transactions…</div>
        ) : visible.length === 0 ? (
          <div className="p-12 text-center text-gray-400">
            {tab === 'hsa'
              ? 'No HSA transactions yet. Switch to "All Transactions" and click Mark on any row.'
              : 'No transactions found. Connect a bank account and sync to get started.'}
          </div>
        ) : (
          visible.map(txn => (
            <TxnRow
              key={txn.id}
              txn={txn}
              members={members}
              showCategory={tab === 'hsa'}
              onChange={handleChange}
            />
          ))
        )}
      </div>

      {visible.length > 0 && (
        <p className="text-xs text-gray-400 mt-3 text-right">
          {visible.length} transaction{visible.length !== 1 ? 's' : ''}
          {visible.length < transactions.length ? ` (filtered from ${transactions.length})` : ''}
        </p>
      )}
    </div>
  )
}
