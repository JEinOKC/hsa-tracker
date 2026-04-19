import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { bankService } from '../services/bank'
import { useToast } from '../components/Toast'

const STORAGE_KEY = 'hsa_last_auto_sync'
const INTERVAL_STORAGE_KEY = 'hsa_sync_interval_ms'
const DEFAULT_INTERVAL_MS = 24 * 60 * 60 * 1000

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

      const errors: string[] = []

      await Promise.allSettled(
        stale.map(async account => {
          try {
            await bankService.syncAccount(account.id)
          } catch (err: any) {
            const status = err?.response?.status
            const name = account.institution_name || account.account_name
            if (status === 422) {
              errors.push(`${name} needs to be reconnected`)
            } else {
              errors.push(`${name} failed to sync`)
            }
          }
        })
      )

      if (errors.length > 0) {
        errors.forEach(msg => {
          toast(msg, 'error', {
            label: 'Go to Bank Accounts',
            onClick: () => navigate('/bank'),
          })
        })
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
