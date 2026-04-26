import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { bankService, DashboardSummary } from '../services/bank'
import { portfolioService, PortfolioSummary } from '../services/portfolio'

function formatDollars(amount: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Math.abs(amount))
}

type RangeKey = '1D' | '1W' | '1M' | '3M' | '6M' | 'YTD' | '1Y' | '2Y' | '5Y' | '10Y' | 'ALL'

const RANGES: RangeKey[] = ['1D', '1W', '1M', '3M', '6M', 'YTD', '1Y', '2Y', '5Y', '10Y', 'ALL']

function startDateForRange(range: RangeKey): string | undefined {
  const today = new Date()
  const iso = (d: Date) => d.toISOString().slice(0, 10)

  switch (range) {
    case '1D':  return iso(today)
    case '1W': { const d = new Date(today); d.setDate(d.getDate() - 7); return iso(d) }
    case '1M': { const d = new Date(today); d.setMonth(d.getMonth() - 1); return iso(d) }
    case '3M': { const d = new Date(today); d.setMonth(d.getMonth() - 3); return iso(d) }
    case '6M': { const d = new Date(today); d.setMonth(d.getMonth() - 6); return iso(d) }
    case 'YTD': return `${today.getFullYear()}-01-01`
    case '1Y': { const d = new Date(today); d.setFullYear(d.getFullYear() - 1); return iso(d) }
    case '2Y': { const d = new Date(today); d.setFullYear(d.getFullYear() - 2); return iso(d) }
    case '5Y': { const d = new Date(today); d.setFullYear(d.getFullYear() - 5); return iso(d) }
    case '10Y': { const d = new Date(today); d.setFullYear(d.getFullYear() - 10); return iso(d) }
    case 'ALL': return undefined
  }
}

interface SetupStep {
  label: string
  description: string
  done: boolean
  link: string
  linkLabel: string
}

export default function Dashboard() {
  const [range, setRange] = useState<RangeKey>('YTD')
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null)

  useEffect(() => {
    setLoading(true)
    bankService.getDashboardSummary({ start_date: startDateForRange(range) })
      .then(setSummary)
      .finally(() => setLoading(false))
  }, [range])

  useEffect(() => {
    portfolioService.getSummary().then(setPortfolio).catch(() => {})
  }, [])

  const steps: SetupStep[] = summary ? [
    {
      label: 'Add family members',
      description: 'Set up the people covered under your HSA plan.',
      done: summary.has_family_members,
      link: '/family',
      linkLabel: 'Manage family →',
    },
    {
      label: 'Connect a bank account',
      description: 'Link your accounts via Teller to import transactions automatically.',
      done: summary.has_bank_connections,
      link: '/bank-accounts',
      linkLabel: 'Connect account →',
    },
    {
      label: 'Sync transactions',
      description: 'Pull in your latest transactions from connected accounts.',
      done: summary.has_synced_transactions,
      link: '/bank-accounts',
      linkLabel: 'Sync now →',
    },
    {
      label: 'Flag HSA transactions',
      description: 'Review your transactions and mark eligible expenses.',
      done: summary.has_hsa_transactions,
      link: '/transactions',
      linkLabel: 'Review transactions →',
    },
  ] : []

  const allDone = steps.length > 0 && steps.every(s => s.done)

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl">
      <header className="mb-6">
        <h1 className="text-2xl sm:text-4xl font-bold text-gray-900 mb-1">HSA Tracker</h1>
        <p className="text-gray-500">Your self-hosted HSA expense tracker</p>
      </header>

      {/* Range selector — horizontally scrollable on mobile */}
      <div className="flex gap-1 mb-6 border-b border-gray-200 pb-3 overflow-x-auto">
        {RANGES.map(r => (
          <button
            key={r}
            onClick={() => setRange(r)}
            className={`px-3 py-1 text-sm font-medium rounded transition-colors ${
              range === r
                ? 'bg-sky-600 text-white'
                : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100'
            }`}
          >
            {r}
          </button>
        ))}
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5 gap-6 mb-8">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500 mb-2">HSA Spending</h3>
          <p className={`text-3xl font-bold ${loading ? 'text-gray-200' : 'text-gray-900'}`}>
            {loading ? '—' : formatDollars(summary?.hsa_spending ?? 0)}
          </p>
          <p className="text-sm text-gray-500 mt-2">
            {!loading && (summary?.hsa_transaction_count
              ? `${summary.hsa_transaction_count} flagged transaction${summary.hsa_transaction_count !== 1 ? 's' : ''}`
              : 'No HSA transactions in this period')}
          </p>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500 mb-2">Pending Reimbursement</h3>
          <p className={`text-3xl font-bold ${loading ? 'text-gray-200' : 'text-gray-900'}`}>
            {loading ? '—' : formatDollars(summary?.pending_reimbursement ?? 0)}
          </p>
          <p className="text-sm text-gray-500 mt-2">
            {!loading && (summary?.pending_reimbursement
              ? <Link data-testid="pending-reimburse-tip" to="/transactions?tab=reimbursed" className="text-sky-600 hover:text-sky-800">Not yet reimbursed · why waiting pays off →</Link>
              : 'All caught up!')}
          </p>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500 mb-2">HSA Transactions</h3>
          <p className={`text-3xl font-bold ${loading ? 'text-gray-200' : 'text-gray-900'}`}>
            {loading ? '—' : (summary?.hsa_transaction_count ?? 0)}
          </p>
          <p className="text-sm text-gray-500 mt-2">
            <Link to="/transactions?tab=hsa" className="text-sky-600 hover:text-sky-800">
              View HSA transactions →
            </Link>
          </p>
        </div>

        {/* Portfolio value card */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500 mb-2">HSA Portfolio</h3>
          <p className="text-3xl font-bold text-gray-900">
            {portfolio?.total_value != null
              ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(
                  Math.abs(parseFloat(portfolio.total_value))
                )
              : '—'}
          </p>
          <p className="text-sm text-gray-500 mt-2">
            {portfolio?.accounts.length
              ? <Link data-testid="portfolio-link" to="/portfolio" className="text-sky-600 hover:text-sky-800">View portfolio →</Link>
              : <Link data-testid="portfolio-setup-link" to="/portfolio" className="text-sky-600 hover:text-sky-800">Set up portfolio →</Link>
            }
          </p>
        </div>

        <div className={`rounded-lg shadow p-6 ${
          !loading && (summary?.undocumented_hsa_count ?? 0) > 0
            ? 'bg-amber-50 border border-amber-200'
            : 'bg-white'
        }`}>
          <h3 className="text-sm font-medium text-gray-500 mb-2">Needs Documentation</h3>
          <p className={`text-3xl font-bold ${
            loading ? 'text-gray-200'
            : (summary?.undocumented_hsa_count ?? 0) > 0 ? 'text-amber-600'
            : 'text-gray-900'
          }`}>
            {loading ? '—' : (summary?.undocumented_hsa_count ?? 0)}
          </p>
          <p className="text-sm text-gray-500 mt-2">
            {!loading && (
              (summary?.undocumented_hsa_count ?? 0) > 0 ? (
                <Link to="/transactions?tab=hsa&docs=missing" className="text-amber-600 hover:text-amber-800 font-medium">
                  Attach receipts →
                </Link>
              ) : 'All HSA expenses documented'
            )}
          </p>
        </div>
      </div>

      {/* Setup checklist — hidden once everything is done */}
      {!loading && !allDone && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Getting Started</h2>
          <div className="space-y-4">
            {steps.map((step, i) => (
              <div key={i} className="flex items-start gap-4">
                <div className={`mt-0.5 flex-shrink-0 h-6 w-6 rounded-full flex items-center justify-center text-sm font-medium ${
                  step.done ? 'bg-green-100 text-green-600' : 'bg-sky-500 text-white'
                }`}>
                  {step.done ? '✓' : i + 1}
                </div>
                <div>
                  <h3 className={`text-base font-medium ${step.done ? 'text-gray-400 line-through' : 'text-gray-900'}`}>
                    {step.label}
                  </h3>
                  {!step.done && (
                    <>
                      <p className="text-sm text-gray-500">{step.description}</p>
                      <Link to={step.link} className="text-sm text-sky-600 hover:text-sky-800">
                        {step.linkLabel}
                      </Link>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
