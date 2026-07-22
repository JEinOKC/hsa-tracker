import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { bankService } from '../services/bank'
import { notifyHsaReview } from '../services/pushNotifications'
import { useToast } from '../components/Toast'

const STORAGE_KEY = 'hsa_last_auto_sync'
const INTERVAL_STORAGE_KEY = 'hsa_sync_interval_ms'
const PUSH_COOLDOWN_KEY = 'hsa_last_push_at'
const DEFAULT_INTERVAL_MS = 24 * 60 * 60 * 1000
const PUSH_COOLDOWN_MS = 12 * 60 * 60 * 1000

const VALID_INTERVALS = [4, 8, 12, 24].map(h => h * 60 * 60 * 1000)

function getSyncIntervalMs(): number {
  const raw = localStorage.getItem(INTERVAL_STORAGE_KEY)
  if (!raw) return DEFAULT_INTERVAL_MS
  const parsed = parseInt(raw, 10)
  return VALID_INTERVALS.includes(parsed) ? parsed : DEFAULT_INTERVAL_MS
}

function isStale(lastSyncedAt: string | null): boolean {
  if (!lastSyncedAt) return true
  return Date.now() - new Date(lastSyncedAt).getTime() > getSyncIntervalMs()
}

function shouldCheck(): boolean {
  const last = localStorage.getItem(STORAGE_KEY)
  if (!last) return true
  return Date.now() - parseInt(last, 10) > getSyncIntervalMs()
}

function markChecked() {
  localStorage.setItem(STORAGE_KEY, Date.now().toString())
}

function isPushCooldownActive(): boolean {
  const last = localStorage.getItem(PUSH_COOLDOWN_KEY)
  if (!last) return false
  return Date.now() - parseInt(last, 10) < PUSH_COOLDOWN_MS
}

function markPushSent() {
  localStorage.setItem(PUSH_COOLDOWN_KEY, Date.now().toString())
}

export function useAutoSync() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const running = useRef(false)

  const runSync = async () => {
    if (running.current) return
    if (!shouldCheck()) return
    running.current = true
    markChecked()

    try {
      const accounts = await bankService.listAccounts()
      const stale = accounts.filter(a => a.is_active && isStale(a.last_synced_at))
      if (stale.length === 0) return

      // Single API call to sync all accounts at once
      const result = await bankService.syncAllAccounts()

      // Surface any sync errors as toasts
      for (const outcome of result.outcomes) {
        if (outcome.status !== 'ok') {
          const msg = outcome.status === 'disconnected'
            ? `${outcome.account_name} needs to be reconnected`
            : `${outcome.account_name} failed to sync`
          toast(msg, 'error', {
            label: 'Go to Bank Accounts',
            onClick: () => navigate('/bank'),
          })
        }
      }

      // Send one batched push for all potential HSA transactions found this session,
      // subject to a 12-hour cooldown to avoid alert fatigue.
      if (!isPushCooldownActive()) {
        const totalPotentialHsa = result.outcomes.reduce((sum, o) =>
          o.status === 'ok' ? sum + (o.added ?? 0) : sum
        , 0)
        if (totalPotentialHsa > 0) {
          markPushSent()
          notifyHsaReview(totalPotentialHsa).catch(() => {})
        }
      }
    } catch {
      // If we can't even list accounts (e.g. no bank connections), skip silently
    } finally {
      running.current = false
    }
  }

  useEffect(() => {
    // Run on mount
    runSync()

    // Re-run when the app comes back into focus
    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') runSync()
    }
    document.addEventListener('visibilitychange', onVisibilityChange)

    // Re-run when the service worker sends a periodic sync trigger
    const onSWMessage = (event: MessageEvent) => {
      if (event.data?.type === 'TRIGGER_SYNC') runSync()
    }
    navigator.serviceWorker?.addEventListener('message', onSWMessage)

    return () => {
      document.removeEventListener('visibilitychange', onVisibilityChange)
      navigator.serviceWorker?.removeEventListener('message', onSWMessage)
    }
  }, [])
}
