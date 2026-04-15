import { useState, useEffect, useCallback } from 'react'
import { rulesService, HsaRule } from '../services/rules'
import { familyService, FamilyMember } from '../services/family'
import RuleEditor from '../components/RuleEditor'

export default function Rules() {
  const [rules, setRules] = useState<HsaRule[]>([])
  const [members, setMembers] = useState<FamilyMember[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editingRule, setEditingRule] = useState<HsaRule | null | undefined>(undefined) // undefined = closed
  const [applyResult, setApplyResult] = useState<string | null>(null)
  const [applying, setApplying] = useState(false)
  const [dragOver, setDragOver] = useState<number | null>(null)
  const [draggedId, setDraggedId] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [ruleList, memberList] = await Promise.all([
        rulesService.list(),
        familyService.list(),
      ])
      setRules(ruleList)
      setMembers(memberList)
    } catch {
      setError('Failed to load rules.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleSave = async (saved: HsaRule) => {
    setRules(prev => {
      const idx = prev.findIndex(r => r.id === saved.id)
      if (idx >= 0) {
        const next = [...prev]
        next[idx] = saved
        return next
      }
      return [...prev, saved].sort((a, b) => a.priority - b.priority || a.created_at.localeCompare(b.created_at))
    })
    setEditingRule(undefined)
    // Auto-apply all rules after save so existing transactions reflect the change immediately
    try {
      const result = await rulesService.applyAll()
      setApplyResult(`Rule saved — updated ${result.updated} transaction${result.updated !== 1 ? 's' : ''}.`)
    } catch {
      // Don't block the save UI on apply failure; the rule was saved successfully
    }
  }

  const handleDelete = async (rule: HsaRule) => {
    if (!confirm(`Delete rule "${rule.name}"?`)) return
    try {
      await rulesService.delete(rule.id)
      setRules(prev => prev.filter(r => r.id !== rule.id))
    } catch {
      setError('Failed to delete rule.')
    }
  }

  const handleApplyAll = async () => {
    setApplying(true)
    setApplyResult(null)
    try {
      const result = await rulesService.applyAll()
      setApplyResult(`Updated ${result.updated} transaction${result.updated !== 1 ? 's' : ''}.`)
    } catch {
      setApplyResult('Failed to apply rules.')
    } finally {
      setApplying(false)
    }
  }

  // ── Drag-to-reorder ───────────────────────────────────────────────────────

  const handleDragStart = (e: React.DragEvent, id: string) => {
    setDraggedId(id)
    e.dataTransfer.effectAllowed = 'move'
  }

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    setDragOver(index)
  }

  const handleDrop = async (e: React.DragEvent, dropIndex: number) => {
    e.preventDefault()
    setDragOver(null)
    if (!draggedId) return

    const dragIndex = rules.findIndex(r => r.id === draggedId)
    if (dragIndex === dropIndex) return

    const reordered = [...rules]
    const [moved] = reordered.splice(dragIndex, 1)
    reordered.splice(dropIndex, 0, moved)

    // Assign new priorities = index * 10 to give room
    const withPriorities = reordered.map((r, i) => ({ ...r, priority: i * 10 }))
    setRules(withPriorities)
    setDraggedId(null)

    try {
      const items = withPriorities.map(r => ({ id: r.id, priority: r.priority }))
      await rulesService.reorder(items)
    } catch {
      setError('Failed to save order.')
      load() // revert
    }
  }

  const handleDragEnd = () => {
    setDraggedId(null)
    setDragOver(null)
  }

  return (
    <div className="container mx-auto px-4 py-6 max-w-3xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Transaction Rules</h1>
          <p className="text-sm text-gray-500 mt-1">
            Auto-flag or annotate transactions based on matching conditions.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleApplyAll}
            disabled={applying}
            className="px-3 py-2 text-sm border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            {applying ? 'Applying…' : 'Re-apply All Rules'}
          </button>
          <button
            onClick={() => setEditingRule(null)}
            className="px-3 py-2 text-sm font-medium bg-sky-600 text-white rounded-lg hover:bg-sky-700"
          >
            + New Rule
          </button>
        </div>
      </div>

      {applyResult && (
        <div className="mb-4 px-4 py-2 rounded-lg bg-sky-50 text-sky-700 text-sm">
          {applyResult}
        </div>
      )}

      {error && (
        <div className="mb-4 px-4 py-2 rounded-lg bg-red-50 text-red-600 text-sm">
          {error}
        </div>
      )}

      {/* Rules list */}
      {loading ? (
        <div className="p-12 text-center text-gray-400">Loading rules…</div>
      ) : rules.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <p className="text-gray-400 mb-4">No rules yet.</p>
          <button
            onClick={() => setEditingRule(null)}
            className="px-4 py-2 text-sm font-medium bg-sky-600 text-white rounded-lg hover:bg-sky-700"
          >
            Create your first rule
          </button>
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 divide-y divide-gray-100">
          {rules.map((rule, index) => (
            <div
              key={rule.id}
              draggable
              onDragStart={e => handleDragStart(e, rule.id)}
              onDragOver={e => handleDragOver(e, index)}
              onDrop={e => handleDrop(e, index)}
              onDragEnd={handleDragEnd}
              className={`flex items-center gap-3 px-4 py-3 transition-colors ${
                dragOver === index ? 'bg-sky-50' : 'hover:bg-gray-50'
              } ${draggedId === rule.id ? 'opacity-50' : ''}`}
            >
              {/* Drag handle */}
              <span
                className="text-gray-300 cursor-grab active:cursor-grabbing select-none text-lg leading-none"
                title="Drag to reorder"
              >
                ⠿
              </span>

              {/* Position badge */}
              <span className="text-xs text-gray-400 w-8 shrink-0">#{index + 1}</span>

              {/* Name + summary */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm text-gray-900 truncate">{rule.name}</span>
                  {!rule.is_active && (
                    <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-400">inactive</span>
                  )}
                </div>
                <p className="text-xs text-gray-400 mt-0.5 truncate">
                  {rule.conditions.length} condition{rule.conditions.length !== 1 ? 's' : ''}
                  {' · '}
                  {rule.actions.length} action{rule.actions.length !== 1 ? 's' : ''}
                </p>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => setEditingRule(rule)}
                  className="text-xs px-2 py-1 rounded border border-gray-200 text-gray-600 hover:bg-gray-100"
                >
                  Edit
                </button>
                <button
                  onClick={() => handleDelete(rule)}
                  className="text-xs px-2 py-1 rounded border border-red-100 text-red-500 hover:bg-red-50"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Rule editor modal */}
      {editingRule !== undefined && (
        <RuleEditor
          rule={editingRule}
          members={members}
          onSave={handleSave}
          onClose={() => setEditingRule(undefined)}
        />
      )}
    </div>
  )
}