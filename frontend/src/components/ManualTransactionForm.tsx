import { useState } from 'react'
import { bankService, BankTransaction, MatchCandidate } from '../services/bank'

interface Props {
  onClose: () => void
  onCreated: (txn: BankTransaction) => void
}

export default function ManualTransactionForm({ onClose, onCreated }: Props) {
  const [date, setDate] = useState('')
  const [amount, setAmount] = useState('')
  const [merchant, setMerchant] = useState('')
  const [description, setDescription] = useState('')

  const [step, setStep] = useState<'form' | 'matches'>('form')
  const [matches, setMatches] = useState<MatchCandidate[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!date || !amount || !merchant) return
    setSubmitting(true)
    setError(null)
    try {
      // Step 1: check for duplicates
      const candidates = await bankService.findMatchingTransactions({
        amount,
        date,
        merchant: merchant || undefined,
      })
      if (candidates.length > 0) {
        setMatches(candidates)
        setStep('matches')
        return
      }
      // No duplicates — create directly
      await createTransaction()
    } catch {
      setError('Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const createTransaction = async () => {
    setSubmitting(true)
    setError(null)
    try {
      const txn = await bankService.createManualTransaction({
        transaction_date: date,
        amount,
        merchant_name: merchant,
        description: description || undefined,
      })
      onCreated(txn)
      onClose()
    } catch {
      setError('Failed to create transaction. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  if (step === 'matches') {
    return (
      <ModalShell onClose={onClose} title="Possible duplicate found">
        <p className="text-sm text-gray-600 mb-3">
          We found {matches.length} transaction{matches.length !== 1 ? 's' : ''} in your synced
          data that might already be this expense. Review them before creating a duplicate.
        </p>
        <ul className="divide-y divide-gray-100 rounded border border-gray-200 mb-4 text-sm">
          {matches.map(m => (
            <li key={m.id} className="px-3 py-2">
              <div className="flex justify-between">
                <span className="font-medium">{m.merchant_name || m.description || '—'}</span>
                <span>${parseFloat(m.amount).toFixed(2)}</span>
              </div>
              <div className="text-xs text-gray-400 mt-0.5">
                {m.transaction_date}
                {m.teller_category && ` · ${m.teller_category}`}
              </div>
            </li>
          ))}
        </ul>
        <div className="flex gap-2 justify-end">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-sm text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50"
          >
            Already in my data — cancel
          </button>
          <button
            onClick={createTransaction}
            disabled={submitting}
            className="px-3 py-1.5 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? 'Creating…' : 'Not the same — create anyway'}
          </button>
        </div>
        {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
      </ModalShell>
    )
  }

  return (
    <ModalShell onClose={onClose} title="Add manual transaction">
      <p className="text-xs text-gray-500 mb-4">
        Use this for expenses on a replaced or deactivated card, or any charge not synced from your bank.
      </p>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label htmlFor="mtf-date" className="block text-xs font-medium text-gray-700 mb-1">Date</label>
          <input
            id="mtf-date"
            type="date"
            required
            value={date}
            onChange={e => setDate(e.target.value)}
            className="w-full text-sm border border-gray-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <div>
          <label htmlFor="mtf-amount" className="block text-xs font-medium text-gray-700 mb-1">Amount ($)</label>
          <input
            id="mtf-amount"
            type="number"
            required
            min="0.01"
            step="0.01"
            placeholder="0.00"
            value={amount}
            onChange={e => setAmount(e.target.value)}
            className="w-full text-sm border border-gray-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <div>
          <label htmlFor="mtf-merchant" className="block text-xs font-medium text-gray-700 mb-1">Merchant</label>
          <input
            id="mtf-merchant"
            type="text"
            required
            placeholder="e.g. Dr. Smith Optometry"
            value={merchant}
            onChange={e => setMerchant(e.target.value)}
            className="w-full text-sm border border-gray-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <div>
          <label htmlFor="mtf-description" className="block text-xs font-medium text-gray-700 mb-1">
            Description <span className="text-gray-400 font-normal">(optional)</span>
          </label>
          <input
            id="mtf-description"
            type="text"
            placeholder="e.g. Annual eye exam"
            value={description}
            onChange={e => setDescription(e.target.value)}
            className="w-full text-sm border border-gray-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        {error && <p className="text-xs text-red-600">{error}</p>}
        <div className="flex gap-2 justify-end pt-1">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-sm text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="px-3 py-1.5 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? 'Checking…' : 'Add transaction'}
          </button>
        </div>
      </form>
    </ModalShell>
  )
}

function ModalShell({ children, onClose, title }: { children: React.ReactNode; onClose: () => void; title: string }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative bg-white rounded-lg shadow-xl p-5 max-w-md w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-semibold text-gray-900">{title}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
        </div>
        {children}
      </div>
    </div>
  )
}
