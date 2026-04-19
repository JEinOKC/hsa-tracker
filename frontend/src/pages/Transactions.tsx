import { useState, useEffect, useCallback, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { bankService, BankTransaction, CategorySmartStatus, HSA_CATEGORIES } from '../services/bank'
import { familyService, FamilyMember } from '../services/family'
import { rulesService, HsaRule } from '../services/rules'
import { householdService, Household } from '../services/household'
import { receiptsService, PharmacyFill, ReceiptLineItem } from '../services/receipts'
import DocumentUpload from '../components/DocumentUpload'
import RuleEditor from '../components/RuleEditor'
import MerchantManager from '../components/MerchantManager'
import ManualTransactionForm from '../components/ManualTransactionForm'

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

// ─── HSA status badge (read-only) ────────────────────────────────────────────

function HsaStatusBadge({ txn }: { txn: BankTransaction }) {
  if (txn.is_hsa_eligible === true)
    return <span data-testid="hsa-badge" className="text-xs font-medium px-2 py-0.5 rounded bg-green-100 text-green-700 shrink-0">HSA</span>
  if (txn.is_hsa_eligible === false)
    return <span data-testid="not-hsa-badge" className="text-xs font-medium px-2 py-0.5 rounded bg-red-50 text-red-500 shrink-0">Not HSA</span>
  return null
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
    <span className="inline-flex items-center gap-1">
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
      {txn.eligibility_warning && txn.family_member_id && (
        <span
          title="Transaction date is outside this member's coverage window"
          className="text-amber-500 text-xs font-bold leading-none select-none"
          aria-label="Outside coverage window"
        >
          ⚠
        </span>
      )}
    </span>
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
      <span className="flex flex-wrap items-center gap-1">
        <input
          type="date"
          value={reimburseDate}
          onChange={e => setReimburseDate(e.target.value)}
          className="text-xs border border-gray-300 rounded px-1 py-0.5 min-w-0"
        />
        <span className="flex items-center gap-1">
          <button onClick={confirm} className="text-xs font-medium px-1.5 py-0.5 rounded bg-purple-600 text-white hover:bg-purple-700">
            Save
          </button>
          <button onClick={() => setPickingDate(false)} className="text-xs text-gray-400 hover:text-gray-600">
            ✕
          </button>
        </span>
      </span>
    )

  return (
    <button onClick={() => setPickingDate(true)} className="text-xs font-medium px-2 py-0.5 rounded bg-gray-100 text-gray-400 hover:bg-gray-200 w-24">
      Reimburse
    </button>
  )
}

// ─── Eligible amount editor ───────────────────────────────────────────────────

interface EligibleAmountEditorProps {
  txn: BankTransaction
  onChange: (updated: BankTransaction) => void
}

function EligibleAmountEditor({ txn, onChange }: EligibleAmountEditorProps) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState('')
  const [saving, setSaving] = useState(false)

  const fullAmount = Math.abs(parseFloat(txn.amount)).toFixed(2)
  const current = txn.eligible_amount ? Math.abs(parseFloat(txn.eligible_amount)).toFixed(2) : null

  const save = async () => {
    const parsed = parseFloat(value)
    if (isNaN(parsed) || parsed <= 0) return
    setSaving(true)
    try {
      // Apply same sign as the original amount (expenses are negative)
      const txnAmount = parseFloat(txn.amount)
      const signed = txnAmount < 0 ? -parsed : parsed
      const updated = await bankService.annotateTransaction(txn.id, {
        eligible_amount: signed.toFixed(2),
      })
      onChange(updated)
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }

  const clear = async () => {
    setSaving(true)
    try {
      const updated = await bankService.annotateTransaction(txn.id, { eligible_amount: null })
      onChange(updated)
    } finally {
      setSaving(false)
    }
  }

  if (saving) return <span className="text-xs text-gray-400">…</span>

  if (editing) {
    return (
      <span className="flex items-center gap-1 flex-wrap">
        <span className="text-xs text-gray-500">Eligible $</span>
        <input
          type="number"
          step="0.01"
          min="0.01"
          max={fullAmount}
          value={value}
          onChange={e => setValue(e.target.value)}
          className="text-xs border border-gray-300 rounded px-1 py-0.5 w-20"
          autoFocus
        />
        <button onClick={save} className="text-xs font-medium px-1.5 py-0.5 rounded bg-green-600 text-white hover:bg-green-700">Save</button>
        <button onClick={() => setEditing(false)} className="text-xs text-gray-400 hover:text-gray-600">✕</button>
      </span>
    )
  }

  return (
    <span className="flex items-center gap-1">
      <span className="text-xs text-gray-500">
        Eligible: {current ? `$${current}` : `$${fullAmount} (full)`}
      </span>
      <button
        onClick={() => { setValue(current ?? fullAmount); setEditing(true) }}
        className="text-xs text-sky-500 hover:text-sky-700"
      >
        edit
      </button>
      {current && (
        <button onClick={clear} className="text-xs text-gray-400 hover:text-gray-600">✕</button>
      )}
    </span>
  )
}

// ─── Tag dialog ───────────────────────────────────────────────────────────────

/** Extract the most useful merchant name from a transaction for rule creation. */
function extractMerchantName(txn: BankTransaction): string | null {
  const details = txn.details as { counterparty?: { name?: string } } | null
  if (details?.counterparty?.name) return details.counterparty.name
  return txn.description || null
}

interface TagDialogProps {
  txn: BankTransaction
  onChange: (updated: BankTransaction) => void
  onHidden: () => void
  onCreateHsaRule: () => void
  onCreateHideRule: () => void
  onClose: () => void
}

function TagDialog({ txn, onChange, onHidden, onCreateHsaRule, onCreateHideRule, onClose }: TagDialogProps) {
  const [step, setStep] = useState<'options' | 'remember-hide' | 'remember-hsa'>('options')
  const [merchantName, setMerchantName] = useState<string | null>(null)
  const [ruleCreating, setRuleCreating] = useState(false)

  const amount = parseFloat(txn.amount)

  const handleMarkHsa = async () => {
    const updated = await bankService.annotateTransaction(txn.id, { is_hsa_eligible: true })
    onChange(updated)
    const merchant = extractMerchantName(txn)
    if (merchant) {
      setMerchantName(merchant)
      setStep('remember-hsa')
    } else {
      onClose()
    }
  }

  const handleMarkNotHsa = async () => {
    const updated = await bankService.annotateTransaction(txn.id, { is_hsa_eligible: false })
    onChange(updated)
    const merchant = extractMerchantName(txn)
    if (merchant) {
      setMerchantName(merchant)
      setStep('remember-hide')
    } else {
      onClose()
    }
  }

  const handleHideOne = async () => {
    await bankService.annotateTransaction(txn.id, { auto_flag: 'hidden' })
    onHidden()  // reload list — hidden transactions are excluded by the API by default
    onClose()
  }

  const handleCreateMerchantHideRule = async () => {
    if (!merchantName) { onClose(); return }
    setRuleCreating(true)
    try {
      await rulesService.create({
        name: `Hide ${merchantName}`,
        priority: 0,
        is_active: true,
        conditions: [{ field: 'counterparty_name', operator: 'contains', value: merchantName }],
        actions: [{ action_type: 'hide' }],
        placement: 'last',
      })
      await rulesService.applyAll()
      onHidden()
    } finally {
      setRuleCreating(false)
      onClose()
    }
  }

  const handleCreateMerchantFlagRule = async () => {
    if (!merchantName) { onClose(); return }
    setRuleCreating(true)
    try {
      await rulesService.create({
        name: `Flag ${merchantName} as potential HSA`,
        priority: 0,
        is_active: true,
        conditions: [{ field: 'counterparty_name', operator: 'contains', value: merchantName }],
        actions: [{ action_type: 'mark_potential' }],
        placement: 'last',
      })
      await rulesService.applyAll()
    } finally {
      setRuleCreating(false)
      onClose()
    }
  }

  const backdrop = "fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
  const card = "bg-white rounded-xl shadow-xl w-full max-w-sm"
  const header = "px-5 py-4 border-b border-gray-200 flex items-center justify-between"

  // Step 2a — offer to hide all from this merchant
  if (step === 'remember-hide' && merchantName) {
    return (
      <div className={backdrop} onClick={e => { if (e.target === e.currentTarget) onClose() }}>
        <div className={card}>
          <div className={header}>
            <h2 className="text-base font-semibold text-gray-900">Remember this merchant?</h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
          </div>
          <div className="px-5 py-4">
            <p className="text-sm text-gray-700 mb-1">
              Want to hide all <span className="font-semibold">{merchantName}</span> transactions?
            </p>
            <p className="text-xs text-gray-400 mb-4">
              A rule will be created to hide this merchant automatically going forward.
            </p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={onClose}
                className="px-3 py-1.5 text-sm text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50"
              >
                No thanks
              </button>
              <button
                onClick={handleCreateMerchantHideRule}
                disabled={ruleCreating}
                className="px-3 py-1.5 text-sm text-white bg-red-600 rounded-md hover:bg-red-700 disabled:opacity-50"
              >
                {ruleCreating ? 'Creating…' : 'Yes, hide all'}
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Step 2b — offer to flag future transactions from this merchant
  if (step === 'remember-hsa' && merchantName) {
    return (
      <div className={backdrop} onClick={e => { if (e.target === e.currentTarget) onClose() }}>
        <div className={card}>
          <div className={header}>
            <h2 className="text-base font-semibold text-gray-900">Remember this merchant?</h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
          </div>
          <div className="px-5 py-4">
            <p className="text-sm text-gray-700 mb-1">
              Flag future <span className="font-semibold">{merchantName}</span> transactions for review?
            </p>
            <p className="text-xs text-gray-400 mb-4">
              A rule will flag new transactions from this merchant as potential HSA for your review.
            </p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={onClose}
                className="px-3 py-1.5 text-sm text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50"
              >
                No thanks
              </button>
              <button
                onClick={handleCreateMerchantFlagRule}
                disabled={ruleCreating}
                className="px-3 py-1.5 text-sm text-white bg-green-600 rounded-md hover:bg-green-700 disabled:opacity-50"
              >
                {ruleCreating ? 'Creating…' : 'Yes, flag them'}
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Step 1 — main options
  return (
    <div
      className={backdrop}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className={card}>
        <div className={header}>
          <h2 className="text-base font-semibold text-gray-900">Tag transaction</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
        </div>
        <div className="px-5 py-4">
          <p className="text-sm text-gray-700 truncate font-medium">{txn.description || '(no description)'}</p>
          <p className={`text-sm font-semibold mt-0.5 ${amount < 0 ? 'text-gray-700' : 'text-green-600'}`}>
            {formatAmount(txn.amount)} · {formatDate(txn.transaction_date)}
          </p>
          <div className="mt-4 space-y-2">
            <button
              onClick={handleMarkHsa}
              className="w-full px-4 py-2.5 text-sm font-medium text-green-700 bg-green-50 rounded-lg hover:bg-green-100 text-left"
            >
              Mark as HSA eligible
              <span className="block text-xs font-normal text-green-500 mt-0.5">Count this charge toward your HSA spending.</span>
            </button>
            <button
              onClick={handleMarkNotHsa}
              className="w-full px-4 py-2.5 text-sm font-medium text-red-600 bg-red-50 rounded-lg hover:bg-red-100 text-left"
            >
              Mark as Not HSA
              <span className="block text-xs font-normal text-red-400 mt-0.5">Exclude this charge from HSA tracking.</span>
            </button>
            <button
              onClick={onCreateHsaRule}
              className="w-full px-4 py-2.5 text-sm font-medium text-sky-700 bg-sky-50 rounded-lg hover:bg-sky-100 text-left"
            >
              Create HSA rule
              <span className="block text-xs font-normal text-sky-500 mt-0.5">Auto-mark similar transactions as HSA eligible.</span>
            </button>
            <button
              onClick={handleHideOne}
              className="w-full px-4 py-2.5 text-sm font-medium text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 text-left"
            >
              Hide this transaction
              <span className="block text-xs font-normal text-gray-400 mt-0.5">Remove it from your list.</span>
            </button>
            <button
              onClick={onCreateHideRule}
              className="w-full px-4 py-2.5 text-sm font-medium text-gray-500 bg-gray-50 rounded-lg hover:bg-gray-100 text-left"
            >
              Create hide rule
              <span className="block text-xs font-normal text-gray-400 mt-0.5">Auto-hide similar transactions in the future.</span>
            </button>
          </div>
          <button onClick={onClose} className="mt-3 w-full text-xs text-center text-gray-400 hover:text-gray-600 py-1">
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Transaction row ──────────────────────────────────────────────────────────

// ─── Pharmacy fills panel ─────────────────────────────────────────────────────

function PharmacyFillsPanel({ transactionId }: { transactionId: string }) {
  const [fills, setFills] = useState<PharmacyFill[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    receiptsService.listTransactionFills(transactionId)
      .then(setFills)
      .catch(() => setFills([]))
      .finally(() => setLoading(false))
  }, [transactionId])

  const handleUnlink = async (fillId: string) => {
    try {
      await receiptsService.unlinkFill(fillId)
      setFills(prev => prev.filter(f => f.id !== fillId))
    } catch {
      // ignore
    }
  }

  if (loading || fills.length === 0) return null

  return (
    <div className="mt-3 pt-3 border-t border-gray-100" data-testid="pharmacy-fills-panel">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Prescription fills</p>
      <div className="space-y-1">
        {fills.map(fill => (
          <div key={fill.id} className="flex items-center justify-between gap-2 text-sm">
            <div className="flex-1 min-w-0">
              <span className="text-gray-900 truncate block">{fill.drug_name}</span>
              {fill.rx_number && (
                <span className="text-xs text-gray-400">Rx #{fill.rx_number}</span>
              )}
            </div>
            <span className="text-gray-500 shrink-0">${parseFloat(fill.amount_paid).toFixed(2)}</span>
            <button
              onClick={() => handleUnlink(fill.id)}
              title="Unlink this fill"
              className="text-xs text-gray-300 hover:text-red-400 shrink-0 transition-colors"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Line items panel ─────────────────────────────────────────────────────────

function LineItemsPanel({ transactionId, onEligibleAmountChange }: {
  transactionId: string
  onEligibleAmountChange?: (amount: string | null) => void
}) {
  const [items, setItems] = useState<ReceiptLineItem[]>([])
  const [loading, setLoading] = useState(true)
  const [importing, setImporting] = useState(false)
  const [showAddForm, setShowAddForm] = useState(false)
  const [newDesc, setNewDesc] = useState('')
  const [newAmount, setNewAmount] = useState('')
  const [newHsa, setNewHsa] = useState<boolean | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    receiptsService.listLineItems(transactionId)
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }, [transactionId])

  const eligibleTotal = items
    .filter(i => i.is_hsa_eligible === true)
    .reduce((sum, i) => sum + parseFloat(i.amount), 0)

  const handleImportCsv = async (file: File) => {
    setImporting(true)
    try {
      const result = await receiptsService.importLineItemsCsv(transactionId, file)
      setItems(result.line_items)
      onEligibleAmountChange?.(result.eligible_total)
    } catch {
      // ignore
    } finally {
      setImporting(false)
    }
  }

  const handleToggleHsa = async (item: ReceiptLineItem) => {
    const next = item.is_hsa_eligible === true ? false : true
    try {
      const updated = await receiptsService.updateLineItem(transactionId, item.id, { is_hsa_eligible: next })
      setItems(prev => prev.map(i => i.id === item.id ? updated : i))
      const newTotal = [...items.map(i => i.id === item.id ? updated : i)]
        .filter(i => i.is_hsa_eligible === true)
        .reduce((s, i) => s + parseFloat(i.amount), 0)
      onEligibleAmountChange?.(newTotal > 0 ? newTotal.toFixed(2) : null)
    } catch {
      // ignore
    }
  }

  const handleDelete = async (itemId: string) => {
    try {
      await receiptsService.deleteLineItem(transactionId, itemId)
      const remaining = items.filter(i => i.id !== itemId)
      setItems(remaining)
      const newTotal = remaining.filter(i => i.is_hsa_eligible === true).reduce((s, i) => s + parseFloat(i.amount), 0)
      onEligibleAmountChange?.(newTotal > 0 ? newTotal.toFixed(2) : null)
    } catch {
      // ignore
    }
  }

  const handleAddItem = async () => {
    if (!newDesc.trim() || !newAmount.trim()) return
    try {
      const item = await receiptsService.createLineItem(transactionId, {
        description: newDesc.trim(),
        amount: newAmount.trim(),
        is_hsa_eligible: newHsa,
      })
      const updated = [...items, item]
      setItems(updated)
      const newTotal = updated.filter(i => i.is_hsa_eligible === true).reduce((s, i) => s + parseFloat(i.amount), 0)
      onEligibleAmountChange?.(newTotal > 0 ? newTotal.toFixed(2) : null)
      setNewDesc('')
      setNewAmount('')
      setNewHsa(null)
      setShowAddForm(false)
    } catch {
      // ignore
    }
  }

  if (loading) return null

  return (
    <div className="mt-3 pt-3 border-t border-gray-100" data-testid="line-items-panel">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Line items</p>
        <div className="flex gap-2">
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={importing}
            className="text-xs text-blue-600 hover:underline disabled:opacity-50"
            data-testid="import-csv-button"
          >
            {importing ? 'Importing…' : 'Import CSV'}
          </button>
          <button
            onClick={() => setShowAddForm(prev => !prev)}
            className="text-xs text-blue-600 hover:underline"
          >
            + Add item
          </button>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          data-testid="line-items-file-input"
          onChange={e => {
            const file = e.target.files?.[0]
            if (file) handleImportCsv(file)
            e.target.value = ''
          }}
        />
      </div>

      {items.length > 0 && (
        <div className="space-y-1 mb-2">
          {items.map(item => (
            <div key={item.id} className="flex items-center gap-2 text-sm">
              <button
                onClick={() => handleToggleHsa(item)}
                title={item.is_hsa_eligible ? 'Mark as not HSA eligible' : 'Mark as HSA eligible'}
                className={`text-xs shrink-0 w-5 h-5 rounded border flex items-center justify-center transition-colors ${
                  item.is_hsa_eligible === true
                    ? 'bg-green-500 border-green-500 text-white'
                    : item.is_hsa_eligible === false
                      ? 'bg-white border-gray-300 text-gray-300'
                      : 'bg-white border-gray-200 text-gray-200'
                }`}
              >
                {item.is_hsa_eligible === true ? '✓' : ''}
              </button>
              <span className="flex-1 text-gray-900 truncate">{item.description}</span>
              <span className="text-gray-500 shrink-0 text-xs">${parseFloat(item.amount).toFixed(2)}</span>
              <button
                onClick={() => handleDelete(item.id)}
                title="Remove item"
                className="text-xs text-gray-200 hover:text-red-400 shrink-0 transition-colors"
              >
                ✕
              </button>
            </div>
          ))}
          {eligibleTotal > 0 && (
            <p className="text-xs text-green-700 font-medium pt-1">
              Eligible: ${eligibleTotal.toFixed(2)}
            </p>
          )}
        </div>
      )}

      {showAddForm && (
        <div className="flex gap-1 mt-1">
          <input
            type="text"
            placeholder="Description"
            value={newDesc}
            onChange={e => setNewDesc(e.target.value)}
            className="flex-1 text-xs border border-gray-200 rounded px-2 py-1 min-w-0"
          />
          <input
            type="text"
            placeholder="Amount"
            value={newAmount}
            onChange={e => setNewAmount(e.target.value)}
            className="w-20 text-xs border border-gray-200 rounded px-2 py-1 text-right"
          />
          <select
            value={newHsa === null ? '' : newHsa ? 'true' : 'false'}
            onChange={e => setNewHsa(e.target.value === '' ? null : e.target.value === 'true')}
            className="text-xs border border-gray-200 rounded px-1 py-1"
          >
            <option value="">HSA?</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
          <button
            onClick={handleAddItem}
            className="text-xs px-2 py-1 rounded bg-blue-600 text-white hover:bg-blue-700"
          >
            Add
          </button>
        </div>
      )}

      {items.length === 0 && !showAddForm && (
        <p className="text-xs text-gray-400">No line items yet.</p>
      )}
    </div>
  )
}

interface TxnRowProps {
  txn: BankTransaction
  members: FamilyMember[]
  tab: Tab
  onChange: (updated: BankTransaction) => void
  onTag?: (txn: BankTransaction) => void
}

function TxnRow({ txn, members, tab, onChange, onTag }: TxnRowProps) {
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
      {/* Whole row is tappable on mobile to reveal annotation controls */}
      <div
        className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 cursor-pointer sm:cursor-default"
        onClick={() => setExpanded(prev => !prev)}
      >
        {/* Date — hidden on mobile, shown inline on sm+ */}
        <span className="hidden sm:inline text-xs text-gray-400 w-24 shrink-0">{formatDate(txn.transaction_date)}</span>

        {/* Description + account (includes date on mobile) */}
        <div className="flex-1 min-w-0">
          <p className="text-sm text-gray-900 truncate">{txn.description || '(no description)'}</p>
          {/* Account info on sm+; date + account on mobile */}
          <p className="text-xs text-gray-400 truncate">
            <span className="sm:hidden">{formatDate(txn.transaction_date)} · </span>
            {txn.institution_name || txn.account_name || ''}
            {txn.account_name && txn.institution_name ? ` · ${txn.account_name}` : ''}
            {txn.owner_display_name && (
              <span className="ml-1.5 text-amber-600">· From: {txn.owner_display_name}</span>
            )}
          </p>
          {/* Badges on their own line so they never truncate the merchant name */}
          {(showNoReceiptBadge || (txn.auto_flag === 'potential_hsa' && txn.is_hsa_eligible === null)) && (
            <div className="flex flex-wrap gap-1 mt-0.5">
              {showNoReceiptBadge && (
                <span title="No receipt attached" className="text-xs font-bold px-1 py-0.5 rounded bg-amber-100 text-amber-600">!</span>
              )}
              {txn.auto_flag === 'potential_hsa' && txn.is_hsa_eligible === null && (
                <span title="Potential HSA expense" className="text-xs font-medium px-1.5 py-0.5 rounded bg-blue-100 text-blue-600">Potential HSA</span>
              )}
            </div>
          )}
        </div>

        {/* Amount (+ eligible sub-note when partial) */}
        <div className="w-20 shrink-0 text-right">
          <span className={`text-sm font-semibold ${amount < 0 ? 'text-gray-900' : 'text-green-600'}`}>
            {formatAmount(txn.amount)}
          </span>
          {txn.eligible_amount && txn.eligible_amount !== txn.amount && (
            <p className="text-xs text-green-600">${Math.abs(parseFloat(txn.eligible_amount)).toFixed(2)} elig.</p>
          )}
        </div>

        {/* Annotation controls — desktop only; shown in expanded panel on mobile */}
        <div className="hidden sm:flex items-center gap-2 shrink-0" onClick={e => e.stopPropagation()}>
          <HsaStatusBadge txn={txn} />
          <MemberPicker txn={txn} members={members} onChange={onChange} />
          {(tab === 'hsa' || tab === 'reimbursed') && <CategoryPicker txn={txn} onChange={onChange} />}
          {(tab === 'hsa' || tab === 'reimbursed') && <ReimburseToggle txn={txn} onChange={onChange} />}
        </div>

        {/* Expand chevron — mobile only hint */}
        <span className="sm:hidden text-gray-300 text-xs shrink-0 select-none">
          {expanded ? '▾' : '›'}
        </span>

        {/* Attachment toggle — stopPropagation so row click doesn't double-toggle */}
        <button
          onClick={(e) => { e.stopPropagation(); setExpanded(prev => !prev) }}
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

        {/* Tag button */}
        {onTag && txn.auto_flag !== 'hidden' && (
          <button
            onClick={(e) => { e.stopPropagation(); onTag(txn) }}
            title="Tag this transaction"
            className="shrink-0 text-xs text-gray-300 hover:text-gray-500 px-1 py-0.5 rounded transition-colors"
          >
            Tag
          </button>
        )}
      </div>

      {/* Expandable panel */}
      {expanded && (
        <div className="px-4 pb-3">
          {/* Annotation controls — mobile only */}
          <div className="sm:hidden flex flex-wrap gap-2 mb-3 pb-3 border-b border-gray-100">
            <HsaStatusBadge txn={txn} />
            <MemberPicker txn={txn} members={members} onChange={onChange} />
            {(tab === 'hsa' || tab === 'reimbursed') && <CategoryPicker txn={txn} onChange={onChange} />}
            {(tab === 'hsa' || tab === 'reimbursed') && <ReimburseToggle txn={txn} onChange={onChange} />}
            {onTag && txn.auto_flag !== 'hidden' && (
              <button
                onClick={() => onTag(txn)}
                className="text-xs font-medium px-2 py-0.5 rounded bg-gray-100 text-gray-500 hover:bg-gray-200"
              >
                Tag
              </button>
            )}
          </div>
          {txn.is_hsa_eligible === true && (
            <div className="mb-3">
              <EligibleAmountEditor txn={txn} onChange={onChange} />
            </div>
          )}
          <DocumentUpload
            transactionId={txn.id}
            onCountChange={handleDocCountChange}
          />
          <PharmacyFillsPanel transactionId={txn.id} />
          <LineItemsPanel
            transactionId={txn.id}
            onEligibleAmountChange={(amount) => onChange({ ...txn, eligible_amount: amount })}
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
  const [household, setHousehold] = useState<Household | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showBackToTop, setShowBackToTop] = useState(false)
  const [showMerchantManager, setShowMerchantManager] = useState(false)
  const [showManualForm, setShowManualForm] = useState(false)

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
  const [showHidden, setShowHidden] = useState(false)
  const [filterAutoFlag, setFilterAutoFlag] = useState('')
  const [filterCategory, setFilterCategory] = useState('')
  const [availableCategories, setAvailableCategories] = useState<string[]>([])
  const [smartStatus, setSmartStatus] = useState<CategorySmartStatus[]>([])
  const [pinSaving, setPinSaving] = useState(false)
  const [totalCount, setTotalCount] = useState<number | null>(null)

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
    include_potential_hsa: tab === 'hsa' ? true : undefined,
    reimbursement_status: tab === 'reimbursed' ? 'reimbursed' : tab === 'hsa' ? 'null' : undefined,
    has_documents: filterDocs === 'missing' ? false : filterDocs === 'attached' ? true : undefined,
    search: debouncedSearch || undefined,
    family_member_id: filterMember || undefined,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    show_hidden: showHidden || undefined,
    auto_flag: filterAutoFlag || undefined,
    show_all_categories: filterCategory === '__all__' ? true : undefined,
    teller_category: (filterCategory && filterCategory !== '__all__') ? filterCategory : undefined,
    limit: PAGE_SIZE,
    offset,
  }), [tab, filterDocs, debouncedSearch, filterMember, startDate, endDate, showHidden, filterAutoFlag, filterCategory])

  const buildCountParams = useCallback(() => {
    const { limit: _l, offset: _o, ...rest } = buildParams(0)
    return rest
  }, [buildParams])

  // Initial / filter-change load — resets the list
  const load = useCallback(async () => {
    setLoading(true)
    setTotalCount(null)
    setError(null)
    try {
      const [txns, fam, hh, cats, count, smartSt] = await Promise.all([
        bankService.listAllTransactions(buildParams(0)),
        familyService.list(),
        householdService.getMine(),
        bankService.listTransactionCategories(),
        bankService.countTransactions(buildCountParams()),
        bankService.getSmartFilterStatus(),
      ])
      setTransactions(txns)
      setMembers(fam)
      setHousehold(hh)
      setAvailableCategories(cats)
      setTotalCount(count)
      setSmartStatus(smartSt)
      setHasMore(txns.length === PAGE_SIZE)
    } catch {
      setError('Failed to load transactions.')
    } finally {
      setLoading(false)
    }
  }, [buildParams, buildCountParams])

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

  // ── Tag flow ──────────────────────────────────────────────────────────────
  const [tagPromptTxn, setTagPromptTxn] = useState<BankTransaction | null>(null)
  const [ruleEditorTxn, setRuleEditorTxn] = useState<BankTransaction | null>(null)
  const [ruleEditorAction, setRuleEditorAction] = useState<'hide' | 'mark_hsa'>('hide')
  const [ruleSuccessMsg, setRuleSuccessMsg] = useState<string | null>(null)

  const handleRuleSave = async (rule: HsaRule) => {
    setRuleEditorTxn(null)
    try {
      const result = await rulesService.applyAll()
      await load()
      setRuleSuccessMsg(
        `Rule "${rule.name}" created — ${result.updated} transaction(s) updated. You can edit or delete it anytime in Settings → Rules.`
      )
    } catch {
      setRuleSuccessMsg(
        `Rule "${rule.name}" created. You can edit or delete it anytime in Settings → Rules.`
      )
    }
  }

  const switchTab = (next: Tab) => {
    setSearchParams(next === 'all' ? {} : { tab: next })
    setSearch('')
    setDebouncedSearch('')
    setFilterMember('')
    setStartDate('')
    setEndDate('')
    setShowHidden(false)
    setFilterAutoFlag('')
    setFilterCategory('')
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
    setShowHidden(false)
    setFilterAutoFlag('')
    setFilterCategory('')
    setSearchParams(tab !== 'all' ? { tab } : {})
  }

  const strict = household?.strict_eligibility ?? false
  const tabTotal = (tab === 'hsa' || tab === 'reimbursed')
    ? transactions
        .filter(t => !strict || !t.eligibility_warning)
        .reduce((sum, t) => sum + parseFloat(t.amount), 0)
    : null

  const hasFilters = !!(search || filterMember || startDate || endDate || filterDocs || showHidden || filterAutoFlag || (filterCategory && filterCategory !== '__all__'))

  return (
    <>
    {/* Merchant manager drawer */}
    {showMerchantManager && (
      <MerchantManager
        onClose={() => setShowMerchantManager(false)}
        onHidden={() => load()}
      />
    )}

    {/* Manual transaction form */}
    {showManualForm && (
      <ManualTransactionForm
        onClose={() => setShowManualForm(false)}
        onCreated={txn => setTransactions(prev => [txn, ...prev])}
      />
    )}

    {/* Tag dialog */}
    {tagPromptTxn && (
      <TagDialog
        txn={tagPromptTxn}
        onChange={handleChange}
        onHidden={() => load()}
        onCreateHsaRule={() => { setRuleEditorAction('mark_hsa'); setRuleEditorTxn(tagPromptTxn); setTagPromptTxn(null) }}
        onCreateHideRule={() => { setRuleEditorAction('hide'); setRuleEditorTxn(tagPromptTxn); setTagPromptTxn(null) }}
        onClose={() => setTagPromptTxn(null)}
      />
    )}

    {/* Quick rule editor */}
    {ruleEditorTxn && (
      <RuleEditor
        rule={null}
        members={members}
        availableCategories={availableCategories}
        initialName={`${ruleEditorAction === 'mark_hsa' ? 'HSA' : 'Hide'}: ${ruleEditorTxn.description || 'transaction'}`}
        initialConditions={[{ field: 'description', operator: 'is', value: ruleEditorTxn.description || '' }]}
        initialActions={[{ action_type: ruleEditorAction, member_id: null }]}
        onSave={handleRuleSave}
        onClose={() => setRuleEditorTxn(null)}
      />
    )}

    <div className="container mx-auto px-4 py-4 sm:py-8 max-w-5xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-4 sm:mb-6 flex-wrap">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Transactions</h1>
          <p className="text-gray-500 mt-1 text-sm sm:text-base">Review and tag transactions as HSA-eligible.</p>
        </div>
        {tabTotal !== null && (
          <div className="text-right shrink-0">
            <p className="text-xs text-gray-400">
              {tab === 'reimbursed' ? 'Reimbursed total' : 'HSA total'}
              {hasMore ? ' (partial)' : ''}
              {strict ? ' · strict' : ''}
            </p>
            <p className={`text-xl font-bold ${tab === 'reimbursed' ? 'text-purple-700' : 'text-green-700'}`}>
              {formatAmount(tabTotal.toFixed(2))}
            </p>
          </div>
        )}
      </div>

      {/* Action buttons */}
      <div className="flex gap-2 mb-3 justify-end">
        <button
          onClick={() => setShowMerchantManager(true)}
          className="text-sm text-gray-600 border border-gray-300 rounded-lg px-3 py-1.5 hover:bg-gray-50"
        >
          Manage merchants
        </button>
        <button
          onClick={() => setShowManualForm(true)}
          className="text-sm text-white bg-blue-600 border border-blue-600 rounded-lg px-3 py-1.5 hover:bg-blue-700"
        >
          + Add transaction
        </button>
      </div>

      {/* Tabs */}
      <div className="flex mb-4 border-b border-gray-200">
        {(['all', 'hsa', 'reimbursed'] as Tab[]).map(t => {
          const fullLabel = t === 'all' ? 'All Transactions' : t === 'hsa' ? 'HSA Transactions' : 'Reimbursed'
          const shortLabel = t === 'all' ? 'All' : t === 'hsa' ? 'HSA' : 'Reimbursed'
          return (
            <button
              key={t}
              aria-label={fullLabel}
              onClick={() => switchTab(t)}
              className={`px-3 sm:px-5 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                tab === t
                  ? 'border-sky-600 text-sky-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <span className="sm:hidden" aria-hidden="true">{shortLabel}</span>
              <span className="hidden sm:inline" aria-hidden="true">{fullLabel}</span>
            </button>
          )
        })}
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-2 mb-4">
        <input
          type="text"
          placeholder="Search description…"
          value={search}
          onChange={e => handleSearchChange(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-full sm:w-52 focus:outline-none focus:ring-2 focus:ring-sky-500"
        />
        <div className="grid grid-cols-2 sm:flex sm:flex-wrap gap-2">
          <select
            value={filterMember}
            onChange={e => setFilterMember(e.target.value)}
            className="min-w-0 border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            <option value="">All people</option>
            {members.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
          <select
            value={filterDocs}
            onChange={e => setDocsFilter(e.target.value)}
            className="min-w-0 border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            <option value="">Any docs</option>
            <option value="missing">Missing receipts</option>
            <option value="attached">Has receipts</option>
          </select>
          <select
            value={filterAutoFlag}
            onChange={e => setFilterAutoFlag(e.target.value)}
            className="min-w-0 border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            <option value="">All flags</option>
            <option value="potential_hsa">Potential HSA only</option>
          </select>
          {availableCategories.length > 0 && (
            <select
              value={filterCategory}
              onChange={e => setFilterCategory(e.target.value)}
              className="min-w-0 border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
            >
              <option value="">Smart</option>
              <option value="__all__">All categories</option>
              {availableCategories.map(c => (
                <option key={c} value={c}>{c.replace(/_/g, ' ').replace(/^\w/, l => l.toUpperCase())}</option>
              ))}
            </select>
          )}
          <label className="flex items-center gap-2 cursor-pointer min-w-0 px-1">
            <input
              type="checkbox"
              checked={showHidden}
              onChange={e => setShowHidden(e.target.checked)}
              className="rounded border-gray-300 text-sky-600 focus:ring-sky-500"
            />
            <span className="text-sm text-gray-600 whitespace-nowrap">Show hidden</span>
          </label>
          <div className="col-span-2 sm:col-span-1 min-w-0">
            <label className="block text-xs text-gray-400 mb-1 pl-1">From</label>
            <input
              type="date"
              value={startDate}
              onChange={e => setStartDate(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>
          <div className="col-span-2 sm:col-span-1 min-w-0">
            <label className="block text-xs text-gray-400 mb-1 pl-1">To</label>
            <input
              type="date"
              value={endDate}
              onChange={e => setEndDate(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>
          {hasFilters && (
            <button
              onClick={clearFilters}
              className="col-span-2 sm:col-span-1 text-xs text-gray-400 hover:text-gray-600 px-2 py-1.5 border border-gray-200 rounded-lg sm:border-0"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* Category filter info + Smart override */}
      {filterCategory && filterCategory !== '__all__' && (() => {
        const status = smartStatus.find(s => s.category === filterCategory)
        const catLabel = filterCategory.replace(/_/g, ' ').replace(/^\w/, l => l.toUpperCase())
        const handlePin = async (pin_mode: 'show' | 'hide') => {
          setPinSaving(true)
          try {
            await bankService.setCategoryOverride(filterCategory, pin_mode)
            const updated = await bankService.getSmartFilterStatus()
            setSmartStatus(updated)
          } finally {
            setPinSaving(false)
          }
        }
        const handleUnpin = async () => {
          setPinSaving(true)
          try {
            await bankService.deleteCategoryOverride(filterCategory)
            const updated = await bankService.getSmartFilterStatus()
            setSmartStatus(updated)
          } finally {
            setPinSaving(false)
          }
        }
        return (
          <div className="mb-3 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
            <div className="flex items-start gap-2">
              <span className="shrink-0">⚠</span>
              <span>
                Filtering by <strong>{catLabel}</strong>.
                Older transactions may not have bank-provided category data and won&apos;t appear here even if they are of the same type.
              </span>
            </div>
            {status && (
              <div className="mt-2 flex items-center gap-3 pl-5 flex-wrap">
                <span className="text-amber-700">
                  Smart mode:{' '}
                  <strong>{status.effective_smart_hidden ? 'hidden' : 'shown'}</strong>
                  {status.is_auto_promoted && (
                    <span className="ml-1 font-normal text-amber-600">
                      (auto-promoted — {Math.round(status.hsa_rate * 100)}% HSA, {status.reviewed_count} reviewed)
                    </span>
                  )}
                </span>
                {status.pin_mode ? (
                  <button
                    onClick={handleUnpin}
                    disabled={pinSaving}
                    className="text-xs underline text-amber-700 hover:text-amber-900 disabled:opacity-50"
                  >
                    Remove pin (revert to auto)
                  </button>
                ) : status.effective_smart_hidden ? (
                  <button
                    onClick={() => handlePin('show')}
                    disabled={pinSaving}
                    className="text-xs underline text-amber-700 hover:text-amber-900 disabled:opacity-50"
                  >
                    Always show in Smart mode
                  </button>
                ) : (
                  <button
                    onClick={() => handlePin('hide')}
                    disabled={pinSaving}
                    className="text-xs underline text-amber-700 hover:text-amber-900 disabled:opacity-50"
                  >
                    Always hide in Smart mode
                  </button>
                )}
              </div>
            )}
          </div>
        )
      })()}

      {/* Potential HSA review callout */}
      {tab === 'hsa' && transactions.some(t => t.is_hsa_eligible === null) && (
        <div className="mb-3 flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
          <span className="shrink-0">⚠</span>
          <span>
            Some transactions below are flagged as <strong>Potential HSA</strong> and need your review.
            Click a row to confirm or reject each one.
          </span>
        </div>
      )}

      {/* Rule success toast */}
      {ruleSuccessMsg && (
        <div className="mb-4 flex items-start gap-3 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-800">
          <span className="flex-1">{ruleSuccessMsg}</span>
          <button onClick={() => setRuleSuccessMsg(null)} className="text-green-500 hover:text-green-700 shrink-0 text-base leading-none">&times;</button>
        </div>
      )}

      {/* Column headers — desktop only */}
      <div className="hidden sm:flex items-center gap-3 px-4 py-2 text-xs font-medium text-gray-400 uppercase tracking-wide">
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
              onTag={setTagPromptTxn}
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
            {totalCount !== null
              ? `Showing ${transactions.length} of ${totalCount} transaction${totalCount !== 1 ? 's' : ''}`
              : `${transactions.length} transaction${transactions.length !== 1 ? 's' : ''} loaded`
            }
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
        className="fixed bottom-20 md:bottom-6 right-6 z-40 bg-white border border-gray-200 shadow-md rounded-full px-4 py-2 text-sm text-gray-600 hover:text-sky-600 hover:border-sky-300 transition-colors"
      >
        ↑ Back to top
      </button>
    )}
    </>
  )
}
