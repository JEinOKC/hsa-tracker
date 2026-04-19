import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { bankService, BankTransaction } from '../services/bank'

function formatDate(dateStr: string): string {
  return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  })
}

function formatAmount(amount: string): string {
  return `$${Math.abs(parseFloat(amount)).toFixed(2)}`
}

export default function ReviewQueue() {
  const navigate = useNavigate()
  const [queue, setQueue] = useState<BankTransaction[]>([])
  const [index, setIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    bankService.listAllTransactions({ auto_flag: 'potential_hsa' })
      .then(txns => {
        const unreviewed = txns
          .filter(t => t.is_hsa_eligible === null || t.is_hsa_eligible === undefined)
          .sort((a, b) => b.transaction_date.localeCompare(a.transaction_date))
        setQueue(unreviewed)
      })
      .finally(() => setLoading(false))
  }, [])

  async function handleDecision(isEligible: boolean) {
    const txn = queue[index]
    if (!txn) return
    setBusy(true)
    try {
      await bankService.annotateTransaction(txn.id, { is_hsa_eligible: isEligible })
    } finally {
      setBusy(false)
      setIndex(i => i + 1)
    }
  }

  function handleSkip() {
    setIndex(i => i + 1)
  }

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-16 max-w-lg text-center">
        <p className="text-sm text-gray-500">Loading review queue…</p>
      </div>
    )
  }

  const current = queue[index]
  const total = queue.length
  const done = index >= total

  return (
    <div className="container mx-auto px-4 py-8 max-w-lg">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-900">Review Queue</h1>
        <button
          onClick={() => navigate('/transactions?tab=hsa')}
          className="text-sm text-sky-600 hover:text-sky-700"
        >
          Done Reviewing
        </button>
      </div>

      {done ? (
        <div className="text-center py-16">
          <div className="text-4xl mb-4">✓</div>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">All caught up!</h2>
          <p className="text-sm text-gray-500 mb-6">
            No more transactions to review right now.
          </p>
          <button
            onClick={() => navigate('/transactions?tab=hsa')}
            className="px-4 py-2 bg-sky-600 text-white text-sm font-medium rounded-md hover:bg-sky-700"
          >
            View HSA Transactions
          </button>
        </div>
      ) : (
        <>
          <p className="text-sm text-gray-500 mb-4">
            {index + 1} of {total}
          </p>

          <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
            <p className="text-xs text-gray-400 mb-1">{formatDate(current.transaction_date)}</p>
            <p className="text-base font-semibold text-gray-900 mb-1">{current.description}</p>
            <p className="text-2xl font-bold text-gray-900">{formatAmount(current.amount)}</p>
          </div>

          <p className="text-sm text-gray-600 mb-4">Is this an HSA-eligible expense?</p>

          <div className="flex flex-col gap-3">
            <button
              onClick={() => handleDecision(true)}
              disabled={busy}
              className="w-full py-3 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              HSA Eligible
            </button>
            <button
              onClick={() => handleDecision(false)}
              disabled={busy}
              className="w-full py-3 bg-red-600 text-white font-medium rounded-lg hover:bg-red-700 disabled:opacity-50"
            >
              Not HSA
            </button>
            <button
              onClick={handleSkip}
              disabled={busy}
              className="w-full py-3 bg-white text-gray-700 font-medium rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
            >
              Skip
            </button>
          </div>
        </>
      )}
    </div>
  )
}
