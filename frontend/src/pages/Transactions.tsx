import { useState, useEffect, useCallback, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { bankService, BankTransaction, HSA_CATEGORIES } from '../services/bank'
import { familyService, FamilyMember } from '../services/family'
import DocumentUpload from '../components/DocumentUpload'

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

// ─── Inline reimburse toggle ──────────────────────────────────────────────────

interface ReimburseToggleProps {
  txn: BankTransaction
  onChange: (updated: BankTransaction) => void
}

function ReimburseToggle({ txn, onChange }: ReimburseToggleProps) {
  const [saving, setSaving] = useState(false)
  const [pickingDate, setPickingDate] = useState(false)
  const [reimburseDate, setReimburseDate] = useState(
    () => new Date().toISOString().slice(0, 10)
  )

  const confirm = async () => {
    setSaving(true)
    setPickingDate(false)
    try {
      const updated = await bankService.annotateTransaction(txn.id, {
        reimbursement_status: 'reimbursed',
        reimbursed_at: reimburseDate ? new Date(reimburseDate).toISOString() : undefined,
      })
      onChange(updated)
    } finally {
      setSaving(false)
    }
  }

  const unmark = async () => {
    setSaving(true)
    try {
      const updated = await bankService.annotateTransaction(txn.id, {
        reimbursement_status: null,
        reimbursed_at: null,
      })
      onChange(updated)
    } finally {
      setSaving(false)
    }
  }

  if (saving) return <span className="text-xs text-gray-400 w-24 inline-block text-center">…</span>

  if (txn.reimbursement_status === 'reimbursed')
    return (
      <button onClick={unmark} className="text-xs font-medium px-2 py-0.5 rounded bg-purple-100 text-purple-700 hover:bg-purple-200 w-24">
        Reimbursed
      </button>
    )

  if (pickingDate)
    return (
      <span className="flex items-center gap-1">
        <input
          type="date"
          value={reimburseDate}
          onChange={e => setReimburseDate(e.target.value)}
          className="text-xs border border-gray-300 rounded px-1 py-0.5"
        />
        <button onClick={confirm} className="text-xs font-medium px-1.5 py-0.5 rounded bg-purple-600 text-white hover:bg-purple-700">
          Save
        </button>
        <button onClick={() => setPickingDate(false)} className="text-xs text-gray-400 hover:text-gray-600">
          ✕
        </button>
      </span>
    )

  return (
    <button onClick={() => setPickingDate(true)} className="text-xs font-medium px-2 py-0.5 rounded bg-gray-100 text-gray-400 hover:bg-gray-200 w-24">
      Reimburse
    </button>
  )
}

// ─── Transaction row ──────────────────────────────────────────────────────────

interface TxnRowProps {
  txn: BankTransaction
  members: FamilyMember[]
  tab: Tab
  onChange: (updated: BankTransaction) => void
}

function TxnRow({ txn, members, tab, onChange }: TxnRowProps) {
  const amount = parseFloat(txn.amount)
  const [expanded, setExpanded] = useState(false)
  const [docCount, setDocCount] = useState(txn.document_count ?? 0)

  const handleDocCountChange = (count: number) => {
    setDocCount(count)
    onChange({ ...txn, document_count: count })
  }

  const showNoReceiptBadge = txn.is_hsa_eligible && docCount === 0

  return (
    <div className="border-b border-gray-50 last:border-0">
      <div className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50">
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

        {/* No-receipt warning badge */}
        {showNoReceiptBadge && (
          <span
            title="No receipt attached"
            className="text-xs font-bold px-1.5 py-0.5 rounded bg-amber-100 text-amber-600 shrink-0"
          >
            !
          </span>
        )}

        {/* HSA toggle (not shown on reimbursed tab) */}
        {tab !== 'reimbursed' && (
          <div className="shrink-0">
            <HsaToggle txn={txn} onChange={onChange} />
          </div>
        )}

        {/* Person picker */}
        <div className="shrink-0">
          <MemberPicker txn={txn} members={members} onChange={onChange} />
        </div>

        {/* Category (HSA + reimbursed tabs) */}
        {(tab === 'hsa' || tab === 'reimbursed') && (
          <div className="shrink-0">
            <CategoryPicker txn={txn} onChange={onChange} />
          </div>
        )}

        {/* Reimburse toggle (HSA + reimbursed tabs) */}
        {(tab === 'hsa' || tab === 'reimbursed') && (
          <div className="shrink-0">
            <ReimburseToggle txn={txn} onChange={onChange} />
          </div>
        )}

        {/* Attachment toggle */}
        <button
          onClick={() => setExpanded(e => !e)}
          title={expanded ? 'Hide receipts' : 'Attach receipts'}
          className={`shrink-0 text-sm px-1.5 py-0.5 rounded transition-colors ${
            expanded
              ? 'text-blue-600 bg-blue-50'
              : docCount > 0
                ? 'text-blue-500 hover:bg-blue-50'
                : 'text-gray-300 hover:text-gray-500'
          }`}
        >
          📎{docCount > 0 ? ` ${docCount}` : ''}
        </button>
      </div>

      {/* Expandable document panel */}
      {expanded && (
        <div className="px-4 pb-3">
          <DocumentUpload
            transactionId={txn.id}
            onCountChange={handleDocCountChange}
          />
        </div>
      )}
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

const PAGE_SIZE = 50
type Tab = 'all' | 'hsa' | 'reimbursed'

export default function Transactions() {
  const [searchParams, setSearchParams] = useSearchParams()
  const rawTab = searchParams.get('tab')
  const tab: Tab = rawTab === 'hsa' ? 'hsa' : rawTab === 'reimbursed' ? 'reimbursed' : 'all'
  const rawDocs = searchParams.get('docs')
  const filterDocs = rawDocs === 'missing' ? 'missing' : rawDocs === 'attached' ? 'attached' : ''

  const [transactions, setTransactions] = useState<BankTransaction[]>([])
  const [members, setMembers] = useState<FamilyMember[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showBackToTop, setShowBackToTop] = useState(false)

  useEffect(() => {
    const onScroll = () => setShowBackToTop(window.scrollY > 400)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // Filters (all server-side)
  const [search, setSearch] = useState('')
  const [filterMember, setFilterMember] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  // Debounce search so we don't fire on every keystroke
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const sentinelRef = useRef<HTMLDivElement | null>(null)
  const loadingMoreRef = useRef(false)
  const handleSearchChange = (value: string) => {
    setSearch(value)
    if (debounceTimer.current) clearTimeout(debounceTimer.current)
    debounceTimer.current = setTimeout(() => setDebouncedSearch(value), 300)
  }

  const buildParams = useCallback((offset: number) => ({
    is_hsa_eligible: (tab === 'hsa' || tab === 'reimbursed') ? true : undefined,
    reimbursement_status: tab === 'reimbursed' ? 'reimbursed' : tab === 'hsa' ? 'null' : undefined,
    has_documents: filterDocs === 'missing' ? false : filterDocs === 'attached' ? true : undefined,
    search: debouncedSearch || undefined,
    family_member_id: filterMember || undefined,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    limit: PAGE_SIZE,
    offset,
  }), [tab, filterDocs, debouncedSearch, filterMember, startDate, endDate])

  // Initial / filter-change load — resets the list
  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [txns, fam] = await Promise.all([
        bankService.listAllTransactions(buildParams(0)),
        familyService.list(),
      ])
      setTransactions(txns)
      setMembers(fam)
      setHasMore(txns.length === PAGE_SIZE)
    } catch {
      setError('Failed to load transactions.')
    } finally {
      setLoading(false)
    }
  }, [buildParams])

  useEffect(() => { load() }, [load])

  const loadMore = useCallback(async () => {
    if (loadingMoreRef.current) return
    loadingMoreRef.current = true
    setLoadingMore(true)
    try {
      const more = await bankService.listAllTransactions(buildParams(transactions.length))
      setTransactions(prev => [...prev, ...more])
      setHasMore(more.length === PAGE_SIZE)
    } catch {
      setError('Failed to load more transactions.')
    } finally {
      loadingMoreRef.current = false
      setLoadingMore(false)
    }
  }, [buildParams, transactions.length])

  // Auto-load when sentinel scrolls into view
  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel) return
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) loadMore() },
      { rootMargin: '200px' },
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [loadMore])

  const handleChange = useCallback((updated: BankTransaction) => {
    setTransactions(prev => prev.map(t => t.id === updated.id ? updated : t))
  }, [])

  const switchTab = (next: Tab) => {
    setSearchParams(next === 'all' ? {} : { tab: next })
    setSearch('')
    setDebouncedSearch('')
    setFilterMember('')
    setStartDate('')
    setEndDate('')
  }

  const setDocsFilter = (val: string) => {
    const params: Record<string, string> = {}
    if (tab !== 'all') params.tab = tab
    if (val) params.docs = val
    setSearchParams(params)
  }

  const clearFilters = () => {
    setSearch('')
    setDebouncedSearch('')
    setFilterMember('')
    setStartDate('')
    setEndDate('')
    setSearchParams(tab !== 'all' ? { tab } : {})
  }

  const tabTotal = (tab === 'hsa' || tab === 'reimbursed')
    ? transactions.reduce((sum, t) => sum + parseFloat(t.amount), 0)
    : null

  const hasFilters = !!(search || filterMember || startDate || endDate || filterDocs)

  return (
    <>
    <div className="container mx-auto px-4 py-8 max-w-5xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Transactions</h1>
          <p className="text-gray-500 mt-1">Review and tag transactions as HSA-eligible.</p>
        </div>
        {tabTotal !== null && (
          <div className="text-right">
            <p className="text-xs text-gray-400">
              {tab === 'reimbursed' ? 'Reimbursed total' : 'HSA total'}
              {hasMore ? ' (partial)' : ''}
            </p>
            <p className={`text-xl font-bold ${tab === 'reimbursed' ? 'text-purple-700' : 'text-green-700'}`}>
              {formatAmount(tabTotal.toFixed(2))}
            </p>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-gray-200">
        {(['all', 'hsa', 'reimbursed'] as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => switchTab(t)}
            className={`px-5 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t
                ? 'border-sky-600 text-sky-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {t === 'all' ? 'All Transactions' : t === 'hsa' ? 'HSA Transactions' : 'Reimbursed'}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 mb-4">
        <input
          type="text"
          placeholder="Search description…"
          value={search}
          onChange={e => handleSearchChange(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-52 focus:outline-none focus:ring-2 focus:ring-sky-500"
        />
        <select
          value={filterMember}
          onChange={e => setFilterMember(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
        >
          <option value="">All people</option>
          {members.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
        </select>
        <input
          type="date"
          value={startDate}
          onChange={e => setStartDate(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
        />
        <span className="self-center text-gray-400 text-sm">to</span>
        <input
          type="date"
          value={endDate}
          onChange={e => setEndDate(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
        />
        <select
          value={filterDocs}
          onChange={e => setDocsFilter(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
        >
          <option value="">Any docs</option>
          <option value="missing">Missing receipts</option>
          <option value="attached">Has receipts</option>
        </select>
        {hasFilters && (
          <button
            onClick={clearFilters}
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
        {tab !== 'reimbursed' && <span className="w-16 shrink-0">HSA?</span>}
        <span className="w-[110px] shrink-0">Person</span>
        {(tab === 'hsa' || tab === 'reimbursed') && <span className="w-[130px] shrink-0">Category</span>}
        {(tab === 'hsa' || tab === 'reimbursed') && <span className="w-24 shrink-0">Reimbursed?</span>}
        <span className="shrink-0">📎</span>
      </div>

      {/* Body */}
      <div className="bg-white rounded-lg shadow">
        {error && (
          <div className="p-6 text-red-600 text-sm">{error}</div>
        )}
        {loading ? (
          <div className="p-12 text-center text-gray-400">Loading transactions…</div>
        ) : transactions.length === 0 ? (
          <div className="p-12 text-center text-gray-400">
            {tab === 'reimbursed'
              ? 'No reimbursed transactions yet. Switch to "HSA Transactions" and click Reimburse on any row.'
              : tab === 'hsa'
                ? 'No HSA transactions yet. Switch to "All Transactions" and click Mark on any row.'
                : hasFilters
                  ? 'No transactions match your filters.'
                  : 'No transactions found. Connect a bank account and sync to get started.'}
          </div>
        ) : (
          transactions.map(txn => (
            <TxnRow
              key={txn.id}
              txn={txn}
              members={members}
              tab={tab}
              onChange={handleChange}
            />
          ))
        )}
      </div>

      {/* Sentinel for auto infinite-scroll */}
      {!loading && hasMore && (
        <div ref={sentinelRef} className="h-1" />
      )}

      {/* Footer: count + manual fallback button */}
      {!loading && transactions.length > 0 && (
        <div className="mt-3 flex items-center justify-between">
          <p className="text-xs text-gray-400">
            {transactions.length} transaction{transactions.length !== 1 ? 's' : ''} loaded
            {hasMore ? ' — scroll for more' : ''}
          </p>
          {hasMore && (
            <button
              onClick={loadMore}
              disabled={loadingMore}
              className="text-xs text-gray-400 hover:text-sky-600 disabled:opacity-50"
            >
              {loadingMore ? 'Loading…' : 'Load more'}
            </button>
          )}
        </div>
      )}
    </div>

    {/* Back to top */}
    {showBackToTop && (
      <button
        onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
        className="fixed bottom-6 right-6 z-50 bg-white border border-gray-200 shadow-md rounded-full px-4 py-2 text-sm text-gray-600 hover:text-sky-600 hover:border-sky-300 transition-colors"
      >
        ↑ Back to top
      </button>
    )}
    </>
  )
}
