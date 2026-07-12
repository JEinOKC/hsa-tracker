import { useEffect, useState } from 'react'
import { BankTransaction } from '../services/bank'
import { bankService } from '../services/bank'
import { lmnService, LmnDocument } from '../services/lmn'

interface Props {
  txn: BankTransaction
  onChange: (updated: BankTransaction) => void
}

export default function LmnPicker({ txn, onChange }: Props) {
  const [lmnDocs, setLmnDocs] = useState<LmnDocument[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    lmnService.listAll()
      .then(setLmnDocs)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const handleChange = async (value: string) => {
    const lmn_document_id = value || null
    try {
      const updated = await bankService.annotateTransaction(txn.id, { lmn_document_id })
      onChange(updated)
    } catch {
      // silently fail — the dropdown will stay on the old value
    }
  }

  if (loading) return null

  // Sort: member-matching LMNs first if family_member_id is set
  const sorted = [...lmnDocs].sort((a, b) => {
    if (txn.family_member_id) {
      const aMatch = a.family_member_id === txn.family_member_id ? 0 : 1
      const bMatch = b.family_member_id === txn.family_member_id ? 0 : 1
      if (aMatch !== bMatch) return aMatch - bMatch
    }
    return a.family_member_name.localeCompare(b.family_member_name)
  })

  if (sorted.length === 0) return null

  return (
    <div className="flex items-center gap-2">
      <label className="text-xs text-gray-500 whitespace-nowrap" htmlFor={`lmn-${txn.id}`}>
        LMN:
      </label>
      <select
        id={`lmn-${txn.id}`}
        value={txn.lmn_document_id || ''}
        onChange={e => handleChange(e.target.value)}
        className="text-xs border border-gray-300 rounded px-1.5 py-1 bg-white truncate max-w-[200px]"
      >
        <option value="">None</option>
        {sorted.map(doc => (
          <option key={doc.id} value={doc.id}>
            {doc.family_member_name}: {doc.label || doc.original_filename}
            {doc.expiration_date && ` (exp ${doc.expiration_date})`}
          </option>
        ))}
      </select>
    </div>
  )
}
