import { useState } from 'react'
import { HsaRule, HsaRuleInput, RuleCondition, RuleAction, PreviewResult } from '../services/rules'
import { FamilyMember } from '../services/family'
import { rulesService } from '../services/rules'

// ─── Types ────────────────────────────────────────────────────────────────────

type ConditionField = RuleCondition['field']
type ConditionOperator = RuleCondition['operator']
type ActionType = RuleAction['action_type']

// ─── Operator options by field type ──────────────────────────────────────────

const TEXT_OPERATORS: { value: ConditionOperator; label: string }[] = [
  { value: 'is', label: 'is exactly' },
  { value: 'is_not', label: 'is not' },
  { value: 'contains', label: 'contains' },
  { value: 'does_not_contain', label: 'does not contain' },
]

const AMOUNT_OPERATORS: { value: ConditionOperator; label: string }[] = [
  { value: 'eq', label: 'equals' },
  { value: 'gt', label: 'greater than' },
  { value: 'lt', label: 'less than' },
]

const DATE_OPERATORS: { value: ConditionOperator; label: string }[] = [
  { value: 'before', label: 'before' },
  { value: 'after', label: 'after' },
]

function operatorsForField(field: ConditionField) {
  if (field === 'amount') return AMOUNT_OPERATORS
  if (field === 'date') return DATE_OPERATORS
  return TEXT_OPERATORS
}

function defaultOperatorForField(field: ConditionField): ConditionOperator {
  if (field === 'amount') return 'eq'
  if (field === 'date') return 'before'
  return 'contains'
}

// ─── Props ────────────────────────────────────────────────────────────────────

interface RuleEditorProps {
  rule: HsaRule | null
  members: FamilyMember[]
  availableCategories?: string[]
  onSave: (rule: HsaRule) => void
  onClose: () => void
  initialName?: string
  initialConditions?: Omit<RuleCondition, 'id' | 'rule_id' | 'created_at'>[]
  initialActions?: Omit<RuleAction, 'id' | 'rule_id' | 'created_at'>[]
}

// ─── Blank row factories ──────────────────────────────────────────────────────

function blankCondition(): Omit<RuleCondition, 'id' | 'rule_id' | 'created_at'> {
  return { field: 'description', operator: 'contains', value: '' }
}

function blankAction(): Omit<RuleAction, 'id' | 'rule_id' | 'created_at'> {
  return { action_type: 'mark_hsa', member_id: null }
}

// ─── Component ────────────────────────────────────────────────────────────────

// Known Sophtron categories shown in the dropdown when no live data is available
const KNOWN_PROVIDER_CATEGORIES = [
  'health', 'personal_care', 'mental_health', 'fitness',
  'food_and_drink', 'shopping', 'travel', 'entertainment',
  'transportation', 'utilities', 'other',
]

export default function RuleEditor({ rule, members, availableCategories, onSave, onClose, initialName, initialConditions, initialActions }: RuleEditorProps) {
  const categoryOptions = availableCategories && availableCategories.length > 0 ? availableCategories : KNOWN_PROVIDER_CATEGORIES
  const [name, setName] = useState(rule?.name ?? initialName ?? '')
  const [isActive, setIsActive] = useState(rule?.is_active ?? true)
  const [conditions, setConditions] = useState<Omit<RuleCondition, 'id' | 'rule_id' | 'created_at'>[]>(
    rule?.conditions?.map(c => ({ field: c.field, operator: c.operator, value: c.value })) ?? initialConditions ?? [blankCondition()]
  )
  const [actions, setActions] = useState<Omit<RuleAction, 'id' | 'rule_id' | 'created_at'>[]>(
    rule?.actions?.map(a => ({ action_type: a.action_type, member_id: a.member_id ?? null })) ?? initialActions ?? [blankAction()]
  )
  const [placement, setPlacement] = useState<'first' | 'last'>('first')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [preview, setPreview] = useState<PreviewResult | 'loading' | null>(null)

  // ── Conditions helpers ───────────────────────────────────────────────────

  const updateCondition = (index: number, patch: Partial<typeof conditions[0]>) => {
    setPreview(null)
    setConditions(prev => prev.map((c, i) => {
      if (i !== index) return c
      const updated = { ...c, ...patch }
      // When field changes, reset operator to a valid default
      if (patch.field && patch.field !== c.field) {
        updated.operator = defaultOperatorForField(patch.field as ConditionField)
      }
      return updated
    }))
  }

  const addCondition = () => { setPreview(null); setConditions(prev => [...prev, blankCondition()]) }
  const removeCondition = (index: number) => {
    setPreview(null)
    setConditions(prev => prev.filter((_, i) => i !== index))
  }

  // ── Actions helpers ───────────────────────────────────────────────────────

  const updateAction = (index: number, patch: Partial<typeof actions[0]>) => {
    setActions(prev => prev.map((a, i) => {
      if (i !== index) return a
      const updated = { ...a, ...patch }
      // Clear member_id when switching away from assign_member
      if (patch.action_type && patch.action_type !== 'assign_member') {
        updated.member_id = null
      }
      return updated
    }))
  }

  const addAction = () => setActions(prev => [...prev, blankAction()])
  const removeAction = (index: number) =>
    setActions(prev => prev.filter((_, i) => i !== index))

  // ── Preview ───────────────────────────────────────────────────────────────

  const handlePreview = async () => {
    setPreview('loading')
    setError(null)
    try {
      const result = await rulesService.preview({
        rule: {
          name: name.trim() || 'Preview',
          priority: rule?.priority ?? 0,
          placement: rule ? undefined : placement,
          is_active: isActive,
          conditions,
          actions,
        },
        rule_id: rule?.id,
      })
      setPreview(result)
    } catch {
      setPreview(null)
      setError('Failed to test rule. Check that all condition values are filled in.')
    }
  }

  // ── Save ──────────────────────────────────────────────────────────────────

  const handleSave = async () => {
    setError(null)
    if (!name.trim()) { setError('Name is required.'); return }
    if (conditions.length === 0) { setError('At least one condition is required.'); return }
    if (actions.length === 0) { setError('At least one action is required.'); return }
    if (conditions.some(c => !c.value.trim())) { setError('All condition values must be filled in.'); return }

    const payload: HsaRuleInput = {
      name: name.trim(),
      priority: rule?.priority ?? 0,
      placement: rule ? undefined : placement,
      is_active: isActive,
      conditions,
      actions,
    }
    setSaving(true)
    try {
      const saved = rule ? await rulesService.update(rule.id, payload) : await rulesService.create(payload)
      onSave(saved)
    } catch {
      setError('Failed to save rule. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">
            {rule ? 'Edit Rule' : 'New Rule'}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
        </div>

        <div className="px-6 py-5 space-y-6">
          {/* Name + active */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Rule name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. Flag pharmacy transactions"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>

          {/* Placement — only for new rules; drag handles existing */}
          {!rule && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Priority</label>
              <div className="inline-flex rounded-lg border border-gray-300 overflow-hidden text-sm">
                <button
                  type="button"
                  onClick={() => setPlacement('first')}
                  className={`px-4 py-2 ${placement === 'first' ? 'bg-sky-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-50'}`}
                >
                  Apply before existing rules
                </button>
                <button
                  type="button"
                  onClick={() => setPlacement('last')}
                  className={`px-4 py-2 border-l border-gray-300 ${placement === 'last' ? 'bg-sky-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-50'}`}
                >
                  Apply after existing rules
                </button>
              </div>
            </div>
          )}

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setIsActive(prev => !prev)}
              aria-pressed={isActive}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-sky-500 ${
                isActive ? 'bg-sky-600' : 'bg-gray-200'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                  isActive ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
            <span className="text-sm text-gray-700">{isActive ? 'Active' : 'Inactive'}</span>
          </div>

          {/* Conditions */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-gray-700">Conditions <span className="text-red-500">*</span> <span className="text-gray-400 font-normal">(ALL must match)</span></h3>
              <button
                type="button"
                onClick={addCondition}
                className="text-xs text-sky-600 hover:text-sky-700 font-medium"
              >
                + Add condition
              </button>
            </div>
            <div className="space-y-2">
              {conditions.map((cond, i) => {
                const ops = operatorsForField(cond.field)
                return (
                  <div key={i} className="flex flex-wrap gap-2 items-center">
                    <select
                      value={cond.field}
                      onChange={e => updateCondition(i, { field: e.target.value as ConditionField })}
                      className="border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-sky-500"
                    >
                      <option value="description">Description</option>
                      <option value="counterparty_name">Merchant</option>
                      <option value="amount">Amount</option>
                      <option value="date">Date</option>
                      <option value="provider_category">Category</option>
                    </select>

                    <select
                      value={cond.operator}
                      onChange={e => updateCondition(i, { operator: e.target.value as ConditionOperator })}
                      className="border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-sky-500"
                    >
                      {ops.map(op => (
                        <option key={op.value} value={op.value}>{op.label}</option>
                      ))}
                    </select>

                    {cond.field === 'provider_category' ? (
                      <select
                        value={cond.value}
                        onChange={e => updateCondition(i, { value: e.target.value })}
                        className="flex-1 min-w-[100px] border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-sky-500"
                      >
                        <option value="">— select category —</option>
                        {categoryOptions.map(cat => (
                          <option key={cat} value={cat}>{cat.replace(/_/g, ' ')}</option>
                        ))}
                      </select>
                    ) : (
                      <input
                        type={cond.field === 'date' ? 'date' : cond.field === 'amount' ? 'number' : 'text'}
                        value={cond.value}
                        onChange={e => updateCondition(i, { value: e.target.value })}
                        placeholder={cond.field === 'amount' ? '-42.00' : cond.field === 'date' ? '' : 'value…'}
                        className="flex-1 min-w-[100px] border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-sky-500"
                      />
                    )}

                    {conditions.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeCondition(i)}
                        className="text-gray-300 hover:text-red-500 text-lg leading-none"
                        aria-label="Remove condition"
                      >
                        &times;
                      </button>
                    )}
                  </div>
                )
              })}
            </div>
          </div>

          {/* Actions */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-gray-700">Actions <span className="text-red-500">*</span></h3>
              <button
                type="button"
                onClick={addAction}
                className="text-xs text-sky-600 hover:text-sky-700 font-medium"
              >
                + Add action
              </button>
            </div>
            <div className="space-y-2">
              {actions.map((action, i) => {
                const otherTypes = actions.filter((_, j) => j !== i).map(a => a.action_type)
                // Flag actions are mutually exclusive — disable the ones already used elsewhere
                const FLAG_ACTIONS: ActionType[] = ['mark_hsa', 'mark_potential', 'hide']
                const usedFlags = otherTypes.filter(t => FLAG_ACTIONS.includes(t))
                const isDisabled = (type: ActionType) =>
                  // Can't pick a flag action already used in another row
                  (FLAG_ACTIONS.includes(type) && usedFlags.includes(type)) ||
                  // Can't add a second assign_member
                  (type === 'assign_member' && otherTypes.includes('assign_member') && action.action_type !== 'assign_member') ||
                  // Can't pick a conflicting flag (all three are mutually exclusive)
                  (FLAG_ACTIONS.includes(type) && usedFlags.some(f => FLAG_ACTIONS.includes(f)) && type !== action.action_type)
                return (
                <div key={i} className="flex flex-wrap gap-2 items-center">
                  <select
                    value={action.action_type}
                    onChange={e => updateAction(i, { action_type: e.target.value as ActionType })}
                    className="border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-sky-500"
                  >
                    <option value="mark_hsa" disabled={isDisabled('mark_hsa')}>Mark as HSA eligible</option>
                    <option value="mark_potential" disabled={isDisabled('mark_potential')}>Flag as potential HSA</option>
                    <option value="hide" disabled={isDisabled('hide')}>Hide transaction</option>
                    <option value="assign_member" disabled={isDisabled('assign_member')}>Assign to family member</option>
                  </select>

                  {action.action_type === 'assign_member' && (
                    <select
                      value={action.member_id ?? ''}
                      onChange={e => updateAction(i, { member_id: e.target.value || null })}
                      className="border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-sky-500"
                    >
                      <option value="">— select member —</option>
                      {members.map(m => (
                        <option key={m.id} value={m.id}>{m.name}</option>
                      ))}
                    </select>
                  )}

                  {actions.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeAction(i)}
                      className="text-gray-300 hover:text-red-500 text-lg leading-none"
                      aria-label="Remove action"
                    >
                      &times;
                    </button>
                  )}
                </div>
              )})}
            </div>
          </div>

          {/* Test this rule */}
          <div>
            <button
              type="button"
              onClick={handlePreview}
              disabled={preview === 'loading' || conditions.some(c => !c.value.trim())}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              {preview === 'loading' ? 'Testing…' : 'Test this rule'}
            </button>

            {preview && preview !== 'loading' && (
              <div className="mt-3 border border-gray-200 rounded-lg overflow-hidden">
                <div className="px-4 py-2 bg-gray-50 border-b border-gray-200 text-sm font-medium text-gray-700">
                  {preview.count === 0
                    ? 'No transactions would be affected'
                    : `${preview.count} transaction${preview.count !== 1 ? 's' : ''} would be affected${preview.capped ? ` (showing first 50)` : ''}`
                  }
                </div>
                {preview.transactions.length > 0 && (
                  <div className="divide-y divide-gray-100 max-h-48 overflow-y-auto">
                    {preview.transactions.map(txn => {
                      const amount = parseFloat(txn.amount)
                      const formatted = isNaN(amount)
                        ? txn.amount
                        : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount)
                      return (
                        <div key={txn.id} className="flex items-center gap-3 px-4 py-2 text-sm">
                          <span className="text-gray-400 shrink-0 w-24">{txn.date}</span>
                          <span className="flex-1 truncate text-gray-800">
                            {txn.counterparty_name || txn.description}
                          </span>
                          <span className={`shrink-0 font-medium tabular-nums ${amount < 0 ? 'text-red-600' : 'text-green-600'}`}>
                            {formatted}
                          </span>
                          {txn.is_hsa_eligible === true && (
                            <span className="shrink-0 text-xs px-1.5 py-0.5 rounded bg-green-100 text-green-700">HSA</span>
                          )}
                          {txn.is_hsa_eligible === false && (
                            <span className="shrink-0 text-xs px-1.5 py-0.5 rounded bg-red-100 text-red-600">Non-HSA</span>
                          )}
                          {txn.is_hsa_eligible === null && txn.auto_flag === 'potential_hsa' && (
                            <span className="shrink-0 text-xs px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">Potential</span>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )}
          </div>

          <p className="text-xs text-gray-400"><span className="text-red-500">*</span> Required</p>

          {error && (
            <p className="text-sm text-red-600">{error}</p>
          )}
        </div>

        <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 text-sm font-medium text-white bg-sky-600 rounded-lg hover:bg-sky-700 disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Save Rule'}
          </button>
        </div>
      </div>
    </div>
  )
}
