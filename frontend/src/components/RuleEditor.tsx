import { useState } from 'react'
import { HsaRule, HsaRuleInput, RuleCondition, RuleAction } from '../services/rules'
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
  onSave: (rule: HsaRule) => void
  onClose: () => void
}

// ─── Blank row factories ──────────────────────────────────────────────────────

function blankCondition(): Omit<RuleCondition, 'id' | 'rule_id' | 'created_at'> {
  return { field: 'description', operator: 'contains', value: '' }
}

function blankAction(): Omit<RuleAction, 'id' | 'rule_id' | 'created_at'> {
  return { action_type: 'mark_hsa', member_id: null }
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function RuleEditor({ rule, members, onSave, onClose }: RuleEditorProps) {
  const [name, setName] = useState(rule?.name ?? '')
  const [priority, setPriority] = useState(rule?.priority ?? 0)
  const [isActive, setIsActive] = useState(rule?.is_active ?? true)
  const [conditions, setConditions] = useState<Omit<RuleCondition, 'id' | 'rule_id' | 'created_at'>[]>(
    rule?.conditions?.map(c => ({ field: c.field, operator: c.operator, value: c.value })) ?? [blankCondition()]
  )
  const [actions, setActions] = useState<Omit<RuleAction, 'id' | 'rule_id' | 'created_at'>[]>(
    rule?.actions?.map(a => ({ action_type: a.action_type, member_id: a.member_id ?? null })) ?? [blankAction()]
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // ── Conditions helpers ───────────────────────────────────────────────────

  const updateCondition = (index: number, patch: Partial<typeof conditions[0]>) => {
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

  const addCondition = () => setConditions(prev => [...prev, blankCondition()])
  const removeCondition = (index: number) =>
    setConditions(prev => prev.filter((_, i) => i !== index))

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

  // ── Save ──────────────────────────────────────────────────────────────────

  const handleSave = async () => {
    setError(null)
    if (!name.trim()) { setError('Name is required.'); return }
    if (conditions.length === 0) { setError('At least one condition is required.'); return }
    if (actions.length === 0) { setError('At least one action is required.'); return }
    if (conditions.some(c => !c.value.trim())) { setError('All condition values must be filled in.'); return }

    const payload: HsaRuleInput = { name: name.trim(), priority, is_active: isActive, conditions, actions }
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
          {/* Name + priority + active */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="sm:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Rule name</label>
              <input
                type="text"
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="e.g. Flag pharmacy transactions"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
              <input
                type="number"
                value={priority}
                onChange={e => setPriority(parseInt(e.target.value) || 0)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
            </div>
          </div>

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
              <h3 className="text-sm font-semibold text-gray-700">Conditions <span className="text-gray-400 font-normal">(ALL must match)</span></h3>
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
                      <option value="counterparty_name">Counterparty name</option>
                      <option value="amount">Amount</option>
                      <option value="date">Date</option>
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

                    <input
                      type={cond.field === 'date' ? 'date' : cond.field === 'amount' ? 'number' : 'text'}
                      value={cond.value}
                      onChange={e => updateCondition(i, { value: e.target.value })}
                      placeholder={cond.field === 'amount' ? '-42.00' : cond.field === 'date' ? '' : 'value…'}
                      className="flex-1 min-w-[100px] border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-sky-500"
                    />

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
              <h3 className="text-sm font-semibold text-gray-700">Actions</h3>
              <button
                type="button"
                onClick={addAction}
                className="text-xs text-sky-600 hover:text-sky-700 font-medium"
              >
                + Add action
              </button>
            </div>
            <div className="space-y-2">
              {actions.map((action, i) => (
                <div key={i} className="flex flex-wrap gap-2 items-center">
                  <select
                    value={action.action_type}
                    onChange={e => updateAction(i, { action_type: e.target.value as ActionType })}
                    className="border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-sky-500"
                  >
                    <option value="mark_hsa">Mark as HSA eligible</option>
                    <option value="mark_potential">Flag as potential HSA</option>
                    <option value="hide">Hide transaction</option>
                    <option value="assign_member">Assign to family member</option>
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
              ))}
            </div>
          </div>

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