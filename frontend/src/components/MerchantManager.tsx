import { useCallback, useEffect, useState } from 'react'
import { XIcon, MedicalIcon } from './icons'
import { bankService, MerchantSummary } from '../services/bank'
import { rulesService } from '../services/rules'

interface Props {
  onClose: () => void
  onHidden: () => void  // called after any hide-all so the transaction list can refresh
}

const SECTION_LABELS: Record<string, string> = {
  unlikely: 'Likely noise',
  unknown: 'Uncategorized',
  likely: 'Possible medical',
}

export default function MerchantManager({ onClose, onHidden }: Props) {
  const [merchants, setMerchants] = useState<MerchantSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [hiding, setHiding] = useState<string | null>(null)
  const [confirmMerchant, setConfirmMerchant] = useState<MerchantSummary | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    bankService.listMerchants()
      .then(setMerchants)
      .catch(() => setError('Failed to load merchants'))
      .finally(() => setLoading(false))
  }, [])

  const filtered = merchants.filter(m =>
    !search || m.normalized_name.toLowerCase().includes(search.toLowerCase())
  )

  // Group by likelihood, preserving backend sort order within each group
  const sections = (['unlikely', 'unknown', 'likely'] as const).map(likelihood => ({
    likelihood,
    items: filtered.filter(m => m.hsa_likelihood === likelihood && !m.has_hsa),
  })).filter(s => s.items.length > 0)

  const handleHideAll = useCallback(async (merchant: MerchantSummary) => {
    setHiding(merchant.normalized_name)
    setError(null)
    try {
      await rulesService.create({
        name: `Hide ${merchant.normalized_name}`,
        priority: 0,
        is_active: true,
        conditions: [{
          field: 'counterparty_name',
          operator: 'contains',
          value: merchant.normalized_name,
        }],
        actions: [{ action_type: 'hide' }],
        placement: 'last',
      })
      await rulesService.applyAll()
      setMerchants(prev => prev.filter(m => m.normalized_name !== merchant.normalized_name))
      onHidden()
    } catch {
      setError(`Failed to hide ${merchant.normalized_name}`)
    } finally {
      setHiding(null)
      setConfirmMerchant(null)
    }
  }, [onHidden])

  const requestHide = (merchant: MerchantSummary) => {
    if (merchant.has_hsa) {
      setConfirmMerchant(merchant)
    } else {
      handleHideAll(merchant)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />

      {/* Drawer */}
      <div className="relative z-10 flex flex-col w-full max-w-md bg-white shadow-xl h-full">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          <h2 className="text-base font-semibold text-gray-900">Manage Merchants</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
            aria-label="Close"
          >
            <XIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Search */}
        <div className="px-4 py-2 border-b border-gray-100">
          <input
            type="text"
            placeholder="Search merchants…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full text-sm border border-gray-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        {/* Stat bar */}
        {!loading && (
          <div className="px-4 py-1.5 text-xs text-gray-500 border-b border-gray-100">
            {filtered.length} merchant{filtered.length !== 1 ? 's' : ''}
            {search ? ` matching "${search}"` : ''}
          </div>
        )}

        {/* Body */}
        <div className="flex-1 overflow-y-auto">
          {loading && (
            <p className="text-sm text-gray-500 text-center py-8">Loading…</p>
          )}

          {!loading && filtered.length === 0 && (
            <p className="text-sm text-gray-500 text-center py-8">
              {search ? 'No merchants match your search.' : 'No merchants found.'}
            </p>
          )}

          {error && (
            <p className="text-xs text-red-600 px-4 py-2">{error}</p>
          )}

          {sections.map(({ likelihood, items }) => (
            <div key={likelihood}>
              <div className="px-4 py-1.5 text-xs font-semibold text-gray-500 uppercase tracking-wide bg-gray-50 border-b border-gray-100 sticky top-0">
                {SECTION_LABELS[likelihood]}
              </div>
              <ul className="divide-y divide-gray-100">
                {items.map(merchant => (
                  <MerchantRow
                    key={merchant.normalized_name}
                    merchant={merchant}
                    hiding={hiding === merchant.normalized_name}
                    onHide={() => requestHide(merchant)}
                  />
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

      {/* HSA warning confirmation */}
      {confirmMerchant && (
        <div className="absolute inset-0 z-20 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={() => setConfirmMerchant(null)} />
          <div className="relative bg-white rounded-lg shadow-xl p-5 max-w-sm w-full mx-4">
            <h3 className="text-sm font-semibold text-gray-900 mb-2">
              HSA transactions exist for this merchant
            </h3>
            <p className="text-sm text-gray-600 mb-4">
              <strong>{confirmMerchant.normalized_name}</strong> has transactions already marked
              as HSA-eligible. Hiding this merchant will hide all{' '}
              <strong>{confirmMerchant.transaction_count}</strong> transactions from this merchant,
              including those HSA-tagged ones. Are you sure?
            </p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setConfirmMerchant(null)}
                className="px-3 py-1.5 text-sm text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={() => handleHideAll(confirmMerchant)}
                className="px-3 py-1.5 text-sm text-white bg-red-600 rounded-md hover:bg-red-700"
              >
                Hide anyway
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function MerchantRow({
  merchant,
  hiding,
  onHide,
}: {
  merchant: MerchantSummary
  hiding: boolean
  onHide: () => void
}) {
  const totalAmt = parseFloat(merchant.total_amount).toFixed(2)

  return (
    <li className="flex items-center justify-between px-4 py-2.5 gap-3 hover:bg-gray-50">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="text-sm text-gray-900 truncate">{merchant.normalized_name}</span>
          {merchant.hsa_likelihood === 'likely' && (
            <span title="This merchant may have HSA-eligible expenses">
              <MedicalIcon className="w-3.5 h-3.5 text-green-600 shrink-0" />
            </span>
          )}
          {merchant.has_hsa && (
            <span
              title="Has HSA-tagged transactions"
              className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-1"
            >
              HSA
            </span>
          )}
        </div>
        <div className="text-xs text-gray-400 mt-0.5">
          {merchant.transaction_count} txn{merchant.transaction_count !== 1 ? 's' : ''} · ${totalAmt}
        </div>
      </div>
      <button
        onClick={onHide}
        disabled={hiding}
        className="text-xs text-red-600 hover:text-red-800 border border-red-200 hover:border-red-400 rounded px-2 py-1 shrink-0 disabled:opacity-50"
      >
        {hiding ? 'Hiding…' : 'Hide all'}
      </button>
    </li>
  )
}
