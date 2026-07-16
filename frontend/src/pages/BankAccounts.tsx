import { useState, useEffect, useCallback } from 'react'
import { bankService, BankAccount, BankTransaction, SyncAllResult } from '../services/bank'
import { useToast } from '../components/Toast'


function formatAmount(amount: string): string {
  const n = parseFloat(amount)
  const abs = Math.abs(n).toFixed(2)
  return n < 0 ? `-$${abs}` : `$${abs}`
}

function formatDate(dateStr: string): string {
  return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  })
}

export default function BankAccounts() {
  const [accounts, setAccounts] = useState<BankAccount[]>([])
  const [selectedAccount, setSelectedAccount] = useState<BankAccount | null>(null)
  const [transactions, setTransactions] = useState<BankTransaction[]>([])
  const [widgetOpen, setWidgetOpen] = useState(false)
  const [setupToken, setSetupToken] = useState('')
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState<string | null>(null)
  const [syncingAll, setSyncingAll] = useState(false)
  const [syncAllResult, setSyncAllResult] = useState<SyncAllResult | null>(null)
  const [connecting, setConnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [txLoading, setTxLoading] = useState(false)
  const { toast } = useToast()

  const loadAccounts = useCallback(async () => {
    try {
      const accts = await bankService.listAccounts()
      setAccounts(accts)
    } catch {
      setError('Failed to load bank accounts.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadAccounts()
  }, [loadAccounts])

  const loadTransactions = useCallback(async (account: BankAccount) => {
    setSelectedAccount(account)
    setTxLoading(true)
    setTransactions([])
    try {
      const txns = await bankService.listTransactions(account.id, { limit: 100 })
      setTransactions(txns)
    } catch {
      setError('Failed to load transactions.')
    } finally {
      setTxLoading(false)
    }
  }, [])

  const handleSync = async (accountId: string) => {
    setSyncing(accountId)
    setError(null)
    try {
      const result = await bankService.syncAccount(accountId)
      toast(`Sync complete: ${result.added} new, ${result.skipped} already stored.`)
      await loadAccounts()
      if (selectedAccount?.id === accountId) {
        const updated = accounts.find(a => a.id === accountId)
        if (updated) loadTransactions(updated)
      }
    } catch (err: unknown) {
      const detail = (err as any)?.response?.data?.detail
      setError(detail ?? 'Sync failed. Check that the account is still connected.')
    } finally {
      setSyncing(null)
    }
  }

  const handleSyncAll = async () => {
    setSyncingAll(true)
    setSyncAllResult(null)
    setError(null)
    try {
      const result = await bankService.syncAllAccounts()
      setSyncAllResult(result)
      if (result.failed > 0) {
        toast(`Sync complete: ${result.succeeded}/${result.total} accounts synced, ${result.failed} failed.`)
      } else {
        toast(`Sync complete: all ${result.total} accounts updated.`)
      }
      await loadAccounts()
    } catch {
      setError('Sync All failed. Please try again.')
    } finally {
      setSyncingAll(false)
    }
  }

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault()
    const token = setupToken.trim()
    if (!token) return
    setConnecting(true)
    setError(null)
    try {
      const newAccounts = await bankService.connect(token)
      toast(`Connected! ${newAccounts.length} account(s) linked.`)
      setWidgetOpen(false)
      setSetupToken('')
      await loadAccounts()
    } catch (err: unknown) {
      const detail = (err as any)?.response?.data?.detail
      setError(detail ?? 'Connection failed. Check your setup token and try again.')
    } finally {
      setConnecting(false)
    }
  }

  const handleDisconnect = async (accountId: string) => {
    if (!confirm('Disconnect this account? Your synced transactions will be kept.')) return
    try {
      await bankService.disconnectAccount(accountId)
      setAccounts(prev => prev.filter(a => a.id !== accountId))
      if (selectedAccount?.id === accountId) {
        setSelectedAccount(null)
        setTransactions([])
      }
    } catch {
      setError('Failed to disconnect account.')
    }
  }

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <p className="text-gray-500">Loading bank accounts…</p>
      </div>
    )
  }

  const disconnectedAccounts = accounts.filter(a => a.connection_status !== 'connected')
  const hasConnectedAccounts = accounts.some(a => a.connection_status === 'connected')

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-start justify-between gap-3 mb-6 flex-wrap">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Bank Accounts</h1>
          <p className="text-gray-500 mt-1">Connect your bank via SimpleFIN to import transactions automatically.</p>
          {syncAllResult && (
            <p className="text-sm text-gray-500 mt-1">
              Last bulk sync: {syncAllResult.succeeded}/{syncAllResult.total} accounts updated
              {syncAllResult.failed > 0 && <span className="text-red-600"> · {syncAllResult.failed} failed</span>}
            </p>
          )}
        </div>
        <div className="flex gap-2 flex-wrap shrink-0">
          <button
            onClick={handleSyncAll}
            disabled={syncingAll || !hasConnectedAccounts}
            className="bg-gray-100 hover:bg-gray-200 disabled:opacity-50 text-gray-700 font-medium px-5 py-2 rounded-lg"
          >
            {syncingAll ? 'Syncing…' : 'Sync All'}
          </button>
          <button
            onClick={() => { setWidgetOpen(true); setError(null) }}
            disabled={connecting}
            className="bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white font-medium px-5 py-2 rounded-lg"
          >
            + Connect Bank
          </button>
        </div>
      </div>

      {/* SimpleFIN setup token modal */}
      {widgetOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Connect via SimpleFIN</h2>
              <button
                onClick={() => { setWidgetOpen(false); setSetupToken('') }}
                className="text-gray-400 hover:text-gray-600 text-xl leading-none"
              >
                ×
              </button>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              Get a setup token from{' '}
              <a
                href="https://beta-bridge.simplefin.org/simplefin/claim"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sky-600 underline"
              >
                SimpleFIN Bridge
              </a>
              , then paste it below. Each token can only be used once.
            </p>
            <form onSubmit={handleConnect}>
              <textarea
                value={setupToken}
                onChange={e => setSetupToken(e.target.value)}
                placeholder="Paste your SimpleFIN setup token here…"
                className="w-full border border-gray-300 rounded-lg p-3 text-sm font-mono resize-none h-24 focus:outline-none focus:ring-2 focus:ring-sky-500"
                disabled={connecting}
                autoFocus
              />
              {error && (
                <p className="text-red-600 text-sm mt-2">{error}</p>
              )}
              <div className="flex justify-end gap-2 mt-4">
                <button
                  type="button"
                  onClick={() => { setWidgetOpen(false); setSetupToken('') }}
                  className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
                  disabled={connecting}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={connecting || !setupToken.trim()}
                  className="bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white font-medium px-5 py-2 rounded-lg text-sm"
                >
                  {connecting ? 'Connecting…' : 'Connect'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {error && !widgetOpen && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 text-red-700 text-sm">
          {error}
        </div>
      )}

      {disconnectedAccounts.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 text-red-700 text-sm flex items-start justify-between gap-4">
          <span>
            {disconnectedAccounts.length === 1
              ? `${disconnectedAccounts[0].account_name} needs to be reconnected.`
              : `${disconnectedAccounts.length} accounts need reconnecting: ${disconnectedAccounts.map(a => a.account_name).join(', ')}.`
            }
          </span>
          <button
            onClick={() => { setWidgetOpen(true); setError(null) }}
            className="underline shrink-0 font-medium"
          >
            Re-connect
          </button>
        </div>
      )}

      {accounts.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <p className="text-gray-400 text-lg mb-2">No bank accounts connected yet.</p>
          <p className="text-gray-400 text-sm">Click "Connect Bank" to link your HSA or checking account via SimpleFIN.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Account list */}
          <div className="lg:col-span-1 space-y-3">
            {accounts.map(account => (
              <div
                key={account.id}
                className={`bg-white rounded-lg shadow p-4 cursor-pointer border-2 transition-colors ${
                  selectedAccount?.id === account.id ? 'border-sky-500' : 'border-transparent hover:border-gray-200'
                }`}
                onClick={() => loadTransactions(account)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-gray-900 truncate">{account.account_name}</p>
                    <p className="text-sm text-gray-500">
                      {account.institution_name}
                      {account.last_four ? ` ····${account.last_four}` : ''}
                    </p>
                    <div className="flex gap-2 mt-1 flex-wrap">
                      {account.account_subtype && (
                        <span className="inline-block text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                          {account.account_subtype.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                        </span>
                      )}
                      {account.account_subtype === 'hsa' && (
                        <span className="inline-block text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded font-medium">
                          HSA
                        </span>
                      )}
                      {account.connection_status === 'disconnected' && (
                        <span className="inline-block text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded font-medium">
                          Disconnected
                        </span>
                      )}
                      {account.connection_status === 'error' && (
                        <span className="inline-block text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded font-medium">
                          Sync Error
                        </span>
                      )}
                      {account.owner_display_name && (
                        <span className="inline-block text-xs bg-amber-50 text-amber-700 px-2 py-0.5 rounded">
                          {account.owner_display_name}'s account
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {account.last_synced_at && (
                  <p className="text-xs text-gray-400 mt-2">
                    Last synced {new Date(account.last_synced_at).toLocaleDateString()}
                  </p>
                )}

                <div className="flex gap-2 mt-3">
                  <button
                    onClick={e => { e.stopPropagation(); handleSync(account.id) }}
                    disabled={syncing === account.id || account.connection_status !== 'connected'}
                    className="flex-1 text-xs bg-sky-50 hover:bg-sky-100 text-sky-700 font-medium py-1.5 rounded disabled:opacity-50"
                    title={account.connection_status !== 'connected' ? 'Re-connect this account before syncing.' : undefined}
                  >
                    {syncing === account.id ? 'Syncing…' : 'Sync'}
                  </button>
                  <button
                    onClick={e => { e.stopPropagation(); handleDisconnect(account.id) }}
                    className="text-xs bg-red-50 hover:bg-red-100 text-red-600 font-medium px-3 py-1.5 rounded"
                  >
                    Disconnect
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Transaction pane */}
          <div className="lg:col-span-2">
            {!selectedAccount ? (
              <div className="bg-white rounded-lg shadow p-12 text-center">
                <p className="text-gray-400">Select an account to view transactions.</p>
              </div>
            ) : (
              <div className="bg-white rounded-lg shadow">
                <div className="px-6 py-4 border-b border-gray-100">
                  <h2 className="text-lg font-semibold text-gray-900">{selectedAccount.account_name}</h2>
                  <p className="text-sm text-gray-500">{selectedAccount.institution_name}</p>
                </div>

                {txLoading ? (
                  <div className="p-8 text-center text-gray-400">Loading transactions…</div>
                ) : transactions.length === 0 ? (
                  <div className="p-8 text-center text-gray-400">
                    No transactions synced yet. Click "Sync" to pull recent transactions.
                  </div>
                ) : (
                  <div className="divide-y divide-gray-50">
                    {transactions.map(txn => (
                      <div key={txn.id} className="px-6 py-3 flex items-center justify-between hover:bg-gray-50">
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-900 truncate">
                            {txn.description || '(no description)'}
                          </p>
                          <p className="text-xs text-gray-400">
                            {formatDate(txn.transaction_date)}
                            {txn.transaction_type ? ` · ${txn.transaction_type.replace('_', ' ')}` : ''}
                          </p>
                        </div>
                        <div className="ml-4 text-right">
                          <p className={`text-sm font-semibold ${parseFloat(txn.amount) < 0 ? 'text-red-600' : 'text-green-600'}`}>
                            {formatAmount(txn.amount)}
                          </p>
                          <span className={`text-xs px-1.5 py-0.5 rounded ${txn.status === 'posted' ? 'bg-green-50 text-green-700' : 'bg-yellow-50 text-yellow-700'}`}>
                            {txn.status}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
