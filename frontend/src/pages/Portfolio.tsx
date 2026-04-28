import { useState, useEffect, useCallback } from 'react'
import {
  portfolioService,
  HsaAccount,
  HsaHolding,
  AccountType,
  ProjectionPoint,
} from '../services/portfolio'
import { PencilIcon, TrashIcon, XIcon, CheckIcon } from '../components/icons'

function formatDollars(value: string | null | undefined): string {
  if (value == null) return '—'
  const n = parseFloat(value)
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n)
}

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return 'never'
  const d = new Date(dateStr)
  const diff = Date.now() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

const ACCOUNT_TYPE_LABELS: Record<AccountType, string> = {
  contribution: 'Contribution',
  investment: 'Investment only',
  both: 'Contribution + Investment',
}

// ─── Add Account Form ─────────────────────────────────────────────────────────

function AddAccountForm({ onCreated }: { onCreated: (account: HsaAccount) => void }) {
  const [institution, setInstitution] = useState('')
  const [nickname, setNickname] = useState('')
  const [accountType, setAccountType] = useState<AccountType>('both')
  const [cashBalance, setCashBalance] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!institution.trim()) return
    setSaving(true)
    setError(null)
    try {
      const created = await portfolioService.createAccount({
        institution_name: institution.trim(),
        nickname: nickname.trim() || undefined,
        account_type: accountType,
        cash_balance: cashBalance ? cashBalance : null,
      })
      onCreated(created)
      setInstitution('')
      setNickname('')
      setAccountType('both')
      setCashBalance('')
    } catch {
      setError('Failed to create account.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      data-testid="add-account-form"
      className="bg-white rounded-lg shadow p-5 border border-dashed border-gray-300"
    >
      <h3 className="text-sm font-semibold text-gray-700 mb-3">Add HSA Account</h3>
      {error && <p className="text-sm text-red-600 mb-2">{error}</p>}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Institution *</label>
          <input
            type="text"
            value={institution}
            onChange={e => setInstitution(e.target.value)}
            placeholder="e.g. Fidelity, Rippling"
            className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
            required
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Nickname (optional)</label>
          <input
            type="text"
            value={nickname}
            onChange={e => setNickname(e.target.value)}
            placeholder="e.g. Old Rippling HSA"
            className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Account type</label>
          <select
            value={accountType}
            onChange={e => setAccountType(e.target.value as AccountType)}
            className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            <option value="both">Contribution + Investment</option>
            <option value="contribution">Contribution only</option>
            <option value="investment">Investment only</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Cash balance ($)</label>
          <input
            type="number"
            value={cashBalance}
            onChange={e => setCashBalance(e.target.value)}
            placeholder="0.00"
            min="0"
            step="0.01"
            className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
          />
        </div>
      </div>
      <button
        type="submit"
        disabled={saving || !institution.trim()}
        className="px-4 py-1.5 text-sm font-medium bg-sky-600 text-white rounded hover:bg-sky-700 disabled:opacity-50"
      >
        {saving ? 'Adding…' : 'Add account'}
      </button>
    </form>
  )
}

// ─── Add Holding Row ──────────────────────────────────────────────────────────

function AddHoldingRow({
  accountId,
  onAdded,
}: {
  accountId: string
  onAdded: (holding: HsaHolding) => void
}) {
  const [ticker, setTicker] = useState('')
  const [shares, setShares] = useState('')
  const [saving, setSaving] = useState(false)
  const [open, setOpen] = useState(false)

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="text-xs text-sky-600 hover:text-sky-800 px-2 py-1"
      >
        + Add holding
      </button>
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!ticker.trim() || !shares) return
    setSaving(true)
    try {
      const created = await portfolioService.addHolding(accountId, {
        ticker: ticker.trim().toUpperCase(),
        shares,
      })
      onAdded(created)
      setTicker('')
      setShares('')
      setOpen(false)
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2 px-2 py-1.5">
      <input
        type="text"
        value={ticker}
        onChange={e => setTicker(e.target.value.toUpperCase())}
        placeholder="Ticker (e.g. VTI)"
        maxLength={20}
        className="border border-gray-300 rounded px-2 py-1 text-xs w-24 focus:outline-none focus:ring-1 focus:ring-sky-500"
        required
      />
      <input
        type="number"
        value={shares}
        onChange={e => setShares(e.target.value)}
        placeholder="Shares"
        min="0.000001"
        step="any"
        className="border border-gray-300 rounded px-2 py-1 text-xs w-24 focus:outline-none focus:ring-1 focus:ring-sky-500"
        required
      />
      <button
        type="submit"
        disabled={saving}
        className="text-xs px-2 py-1 bg-sky-600 text-white rounded hover:bg-sky-700 disabled:opacity-50"
      >
        {saving ? '…' : 'Add'}
      </button>
      <button
        type="button"
        onClick={() => setOpen(false)}
        className="text-xs text-gray-400 hover:text-gray-600"
      >
        Cancel
      </button>
    </form>
  )
}

// ─── Holding Row ──────────────────────────────────────────────────────────────

function HoldingRow({
  holding,
  accountId,
  onUpdated,
  onDelete,
}: {
  holding: HsaHolding
  accountId: string
  onUpdated: (updated: HsaHolding) => void
  onDelete: () => void
}) {
  const [editingPrice, setEditingPrice] = useState(false)
  const [manualPrice, setManualPrice] = useState('')
  const [editingShares, setEditingShares] = useState(false)
  const [manualShares, setManualShares] = useState('')
  const [saving, setSaving] = useState(false)

  const value =
    holding.last_known_price != null
      ? parseFloat(holding.shares) * parseFloat(holding.last_known_price)
      : null

  const saveManualPrice = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!manualPrice) return
    setSaving(true)
    try {
      const updated = await portfolioService.updateHolding(accountId, holding.id, {
        last_known_price: manualPrice,
      })
      onUpdated(updated)
      setEditingPrice(false)
      setManualPrice('')
    } finally {
      setSaving(false)
    }
  }

  const saveManualShares = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!manualShares) return
    setSaving(true)
    try {
      const updated = await portfolioService.updateHolding(accountId, holding.id, {
        shares: manualShares,
      })
      onUpdated(updated)
      setEditingShares(false)
      setManualShares('')
    } finally {
      setSaving(false)
    }
  }

  return (
    <tr className="border-b border-gray-50">
      <td className="py-1 font-medium text-gray-800">{holding.ticker}</td>
      <td className="py-1 text-right text-gray-600">
        {editingShares ? (
          <form onSubmit={saveManualShares} className="flex items-center justify-end gap-1">
            <input
              type="number"
              value={manualShares}
              onChange={e => setManualShares(e.target.value)}
              min="0.000001"
              step="any"
              aria-label={`Shares for ${holding.ticker}`}
              className="w-20 border border-gray-300 rounded px-1 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-sky-500"
              autoFocus
            />
            <button type="submit" disabled={saving} aria-label="Save" className="text-xs text-sky-600 hover:text-sky-800 disabled:opacity-50">
              {saving ? '…' : <CheckIcon className="w-3.5 h-3.5" />}
            </button>
            <button type="button" onClick={() => setEditingShares(false)} aria-label="Cancel" className="text-xs text-gray-400 hover:text-gray-600">
              <XIcon className="w-3.5 h-3.5" />
            </button>
          </form>
        ) : (
          <button
            onClick={() => { setManualShares(parseFloat(holding.shares).toString()); setEditingShares(true) }}
            className="text-gray-600 hover:text-sky-600"
            aria-label={`Edit shares for ${holding.ticker}`}
            title="Click to edit shares"
          >
            {parseFloat(holding.shares).toFixed(4)}
          </button>
        )}
      </td>
      <td className="py-1 text-right text-gray-600">
        {holding.last_known_price != null ? (
          formatDollars(holding.last_known_price)
        ) : editingPrice ? (
          <form onSubmit={saveManualPrice} className="flex items-center justify-end gap-1">
            <input
              type="number"
              value={manualPrice}
              onChange={e => setManualPrice(e.target.value)}
              placeholder="0.00"
              min="0"
              step="0.0001"
              className="w-20 border border-gray-300 rounded px-1 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-sky-500"
              autoFocus
            />
            <button type="submit" disabled={saving} className="text-xs text-sky-600 hover:text-sky-800 disabled:opacity-50">
              {saving ? '…' : <CheckIcon className="w-3.5 h-3.5" />}
            </button>
            <button type="button" onClick={() => setEditingPrice(false)} className="text-xs text-gray-400 hover:text-gray-600">
              <XIcon className="w-3.5 h-3.5" />
            </button>
          </form>
        ) : (
          <button
            onClick={() => setEditingPrice(true)}
            className="text-xs text-gray-300 hover:text-sky-500"
            title="Enter price manually"
          >
            + price
          </button>
        )}
      </td>
      <td className="py-1 text-right text-gray-700">
        {value != null ? formatDollars(String(value.toFixed(2))) : <span className="text-gray-300">—</span>}
      </td>
      <td className="py-1 text-right text-gray-400">{formatRelativeTime(holding.last_price_fetched_at)}</td>
      <td className="py-1 text-right">
        <button
          onClick={onDelete}
          className="text-red-300 hover:text-red-500 leading-none"
          aria-label={`Delete ${holding.ticker}`}
        >
          <XIcon className="w-3.5 h-3.5" />
        </button>
      </td>
    </tr>
  )
}

// ─── Account Card ─────────────────────────────────────────────────────────────

function AccountCard({
  account,
  onUpdated,
  onDeleted,
}: {
  account: HsaAccount
  onUpdated: (account: HsaAccount) => void
  onDeleted: (id: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [editInstitution, setEditInstitution] = useState(account.institution_name)
  const [editNickname, setEditNickname] = useState(account.nickname ?? '')
  const [editCash, setEditCash] = useState(account.cash_balance ?? '')
  const [editType, setEditType] = useState<AccountType>(account.account_type)
  const [savingEdit, setSavingEdit] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [holdings, setHoldings] = useState<HsaHolding[]>(account.holdings)

  // Sync when parent reloads account data (e.g. after price refresh).
  // Use the most recent last_price_fetched_at across all holdings as a
  // stable change signal in addition to the array reference, so a fresh
  // API response always propagates even if React's ref-equality check
  // on the array itself were to be skipped.
  const latestPriceFetch = account.holdings
    .map(h => h.last_price_fetched_at)
    .filter(Boolean)
    .sort()
    .slice(-1)[0] ?? null
  useEffect(() => {
    setHoldings(account.holdings)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [latestPriceFetch, account.holdings])

  const totalInvested = holdings.reduce((sum, h) => {
    if (h.last_known_price == null) return sum
    return sum + parseFloat(h.shares) * parseFloat(h.last_known_price)
  }, 0)

  const totalValue =
    (account.cash_balance ? parseFloat(account.cash_balance) : 0) + totalInvested

  const saveEdit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSavingEdit(true)
    try {
      const updated = await portfolioService.updateAccount(account.id, {
        institution_name: editInstitution.trim(),
        nickname: editNickname.trim() || null,
        account_type: editType,
        cash_balance: editCash !== '' ? String(editCash) : null,
      })
      onUpdated(updated)
      setEditing(false)
    } finally {
      setSavingEdit(false)
    }
  }

  const handleDelete = async () => {
    if (!confirm(`Delete "${account.nickname || account.institution_name}" and all its holdings?`)) return
    setDeleting(true)
    try {
      await portfolioService.deleteAccount(account.id)
      onDeleted(account.id)
    } finally {
      setDeleting(false)
    }
  }

  const handleHoldingAdded = (h: HsaHolding) => setHoldings(prev => [...prev, h])

  const handleDeleteHolding = async (holdingId: string) => {
    await portfolioService.deleteHolding(account.id, holdingId)
    setHoldings(prev => prev.filter(h => h.id !== holdingId))
  }

  return (
    <div className="bg-white rounded-lg shadow p-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div>
          <h3 className="text-base font-semibold text-gray-900">
            {account.nickname || account.institution_name}
          </h3>
          {account.nickname && (
            <p className="text-xs text-gray-500">{account.institution_name}</p>
          )}
          <p className="text-xs text-gray-400 mt-0.5">{ACCOUNT_TYPE_LABELS[account.account_type]}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setEditing(!editing)}
            className="text-base text-gray-400 hover:text-gray-700"
            aria-label="Edit account"
          >
            <PencilIcon />
          </button>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="text-base text-red-400 hover:text-red-600 disabled:opacity-50"
            aria-label="Delete account"
          >
            <TrashIcon />
          </button>
        </div>
      </div>

      {/* Edit form */}
      {editing && (
        <form onSubmit={saveEdit} className="mb-4 p-3 bg-gray-50 rounded border border-gray-200 text-sm">
          <div className="grid grid-cols-2 gap-2 mb-2">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Institution</label>
              <input
                value={editInstitution}
                onChange={e => setEditInstitution(e.target.value)}
                className="w-full border border-gray-300 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-sky-500"
                required
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Nickname</label>
              <input
                value={editNickname}
                onChange={e => setEditNickname(e.target.value)}
                className="w-full border border-gray-300 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-sky-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Type</label>
              <select
                value={editType}
                onChange={e => setEditType(e.target.value as AccountType)}
                className="w-full border border-gray-300 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-sky-500"
              >
                <option value="both">Contribution + Investment</option>
                <option value="contribution">Contribution only</option>
                <option value="investment">Investment only</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Cash balance ($)</label>
              <input
                type="number"
                value={editCash}
                onChange={e => setEditCash(e.target.value)}
                min="0"
                step="0.01"
                className="w-full border border-gray-300 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-sky-500"
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={savingEdit}
              className="text-xs px-3 py-1 bg-sky-600 text-white rounded hover:bg-sky-700 disabled:opacity-50"
            >
              {savingEdit ? 'Saving…' : 'Save'}
            </button>
            <button type="button" onClick={() => setEditing(false)} className="text-xs text-gray-500 hover:text-gray-700">
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Value summary */}
      <div className="flex gap-4 mb-4 text-sm">
        {account.cash_balance != null && (
          <div>
            <p className="text-xs text-gray-400">Cash</p>
            <p className="font-semibold text-gray-800">{formatDollars(account.cash_balance)}</p>
          </div>
        )}
        {holdings.length > 0 && (
          <div>
            <p className="text-xs text-gray-400">Invested</p>
            <p className="font-semibold text-gray-800">
              {totalInvested > 0 ? formatDollars(String(totalInvested.toFixed(2))) : '—'}
            </p>
          </div>
        )}
        {(account.cash_balance != null || totalInvested > 0) && (
          <div>
            <p className="text-xs text-gray-400">Total</p>
            <p className="font-semibold text-sky-700">{formatDollars(String(totalValue.toFixed(2)))}</p>
          </div>
        )}
      </div>

      {/* Holdings table */}
      {holdings.length > 0 && (
        <table className="w-full text-xs mb-2">
          <thead>
            <tr className="text-gray-400 border-b border-gray-100">
              <th className="text-left pb-1">Ticker</th>
              <th className="text-right pb-1">Shares</th>
              <th className="text-right pb-1">Price</th>
              <th className="text-right pb-1">Value</th>
              <th className="text-right pb-1">Updated</th>
              <th className="pb-1"></th>
            </tr>
          </thead>
          <tbody>
            {holdings.map(h => (
              <HoldingRow
                key={h.id}
                holding={h}
                accountId={account.id}
                onUpdated={updated => setHoldings(prev => prev.map(x => x.id === updated.id ? updated : x))}
                onDelete={() => handleDeleteHolding(h.id)}
              />
            ))}
          </tbody>
        </table>
      )}

      {holdings.length === 0 && (
        <p className="text-xs text-gray-400 mb-2">No holdings yet.</p>
      )}

      <AddHoldingRow accountId={account.id} onAdded={handleHoldingAdded} />
    </div>
  )
}

// ─── Projection Calculator ─────────────────────────────────────────────────────

function ProjectionCalculator() {
  const [years, setYears] = useState(20)
  const [annualReturn, setAnnualReturn] = useState(7)
  const [points, setPoints] = useState<ProjectionPoint[]>([])
  const [startingValue, setStartingValue] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const run = useCallback(async () => {
    setLoading(true)
    try {
      const result = await portfolioService.getProjection({ years, annual_return: annualReturn })
      setPoints(result.points)
      setStartingValue(result.starting_value)
    } finally {
      setLoading(false)
    }
  }, [years, annualReturn])

  useEffect(() => { run() }, [run])

  return (
    <div className="bg-white rounded-lg shadow p-5">
      <h2 className="text-base font-semibold text-gray-900 mb-4">Growth Projection</h2>
      <div className="flex flex-wrap gap-4 mb-4 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Years</label>
          <input
            type="number"
            value={years}
            onChange={e => setYears(Math.min(50, Math.max(1, parseInt(e.target.value) || 1)))}
            min={1}
            max={50}
            className="w-20 border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Annual return (%)</label>
          <input
            type="number"
            value={annualReturn}
            onChange={e => setAnnualReturn(Math.min(100, Math.max(0, parseFloat(e.target.value) || 0)))}
            min={0}
            max={100}
            step={0.1}
            className="w-24 border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
          />
        </div>
        {startingValue != null && (
          <p className="text-sm text-gray-500">
            Starting from <strong className="text-gray-800">{formatDollars(startingValue)}</strong>
          </p>
        )}
      </div>

      {loading ? (
        <p className="text-sm text-gray-400">Calculating…</p>
      ) : points.length === 0 ? (
        <p className="text-sm text-gray-400">Add accounts and holdings to see projections.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="text-sm w-full max-w-sm">
            <thead>
              <tr className="text-xs text-gray-400 border-b border-gray-100">
                <th className="text-left pb-1">Year</th>
                <th className="text-right pb-1">Projected Value</th>
              </tr>
            </thead>
            <tbody>
              {points.filter(p => p.year % 5 === 0 || p.year === 1 || p.year === years).map(p => (
                <tr key={p.year} className={`border-b border-gray-50 ${p.year === 0 ? 'font-semibold' : ''}`}>
                  <td className="py-1 text-gray-600">{p.year === 0 ? 'Now' : `Year ${p.year}`}</td>
                  <td className="py-1 text-right text-gray-800">{formatDollars(p.value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ─── Portfolio Page ───────────────────────────────────────────────────────────

export default function Portfolio() {
  const [accounts, setAccounts] = useState<HsaAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [refreshMsg, setRefreshMsg] = useState<string | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)

  useEffect(() => {
    portfolioService.listAccounts()
      .then(setAccounts)
      .catch(() => setError('Failed to load portfolio.'))
      .finally(() => setLoading(false))
  }, [])

  const handleRefreshPrices = async () => {
    setRefreshing(true)
    setRefreshMsg(null)
    try {
      const result = await portfolioService.refreshPrices()
      let msg = `Updated ${result.updated} holding${result.updated !== 1 ? 's' : ''}.`
      if (result.not_found?.length > 0) {
        msg += ` Could not price: ${result.not_found.join(', ')} — enter manually below.`
      }
      setRefreshMsg(msg)
      const updated = await portfolioService.listAccounts()
      setAccounts(updated)
    } catch {
      setRefreshMsg('Price update failed. Check your FINNHUB_API_KEY.')
    } finally {
      setRefreshing(false)
    }
  }

  const handleAccountCreated = (account: HsaAccount) => {
    setAccounts(prev => [...prev, account])
    setShowAddForm(false)
  }

  const handleAccountUpdated = (updated: HsaAccount) => {
    setAccounts(prev => prev.map(a => a.id === updated.id ? updated : a))
  }

  const handleAccountDeleted = (id: string) => {
    setAccounts(prev => prev.filter(a => a.id !== id))
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl">
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-6 gap-3">
        <div>
          <h1 className="text-2xl sm:text-4xl font-bold text-gray-900 mb-1">HSA Portfolio</h1>
          <p className="text-gray-500">Manually track your HSA investments across institutions</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleRefreshPrices}
            disabled={refreshing}
            className="px-3 py-1.5 text-sm font-medium border border-gray-300 rounded-lg text-gray-600 hover:bg-gray-50 disabled:opacity-50"
          >
            {refreshing ? 'Updating…' : 'Update prices'}
          </button>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="px-3 py-1.5 text-sm font-medium bg-sky-600 text-white rounded-lg hover:bg-sky-700"
          >
            + Add account
          </button>
        </div>
      </header>

      {refreshMsg && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-800">
          {refreshMsg}
        </div>
      )}

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      )}

      {showAddForm && (
        <div className="mb-6">
          <AddAccountForm onCreated={handleAccountCreated} />
        </div>
      )}

      {loading ? (
        <div className="text-center text-gray-400 py-12">Loading portfolio…</div>
      ) : accounts.length === 0 ? (
        <div className="text-center text-gray-400 py-12">
          <p className="mb-3">No HSA accounts yet.</p>
          <button
            onClick={() => setShowAddForm(true)}
            className="text-sky-600 hover:text-sky-800 text-sm underline"
          >
            Add your first account →
          </button>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-8">
            {accounts.map(account => (
              <AccountCard
                key={account.id}
                account={account}
                onUpdated={handleAccountUpdated}
                onDeleted={handleAccountDeleted}
              />
            ))}
          </div>

          <ProjectionCalculator />
        </>
      )}

      {/* Pricing note */}
      {accounts.length > 0 && (
        <p className="text-xs text-gray-400 mt-6 text-center">
          Prices are fetched on demand from Finnhub (free API). Click "Update prices" to refresh.
          Holdings without prices show —. Prices are not real-time.
        </p>
      )}
    </div>
  )
}
