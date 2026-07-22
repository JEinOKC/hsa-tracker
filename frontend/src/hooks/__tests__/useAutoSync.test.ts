import { renderHook, act, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
import { useAutoSync } from '../useAutoSync'

const { mockToast, mockNavigate } = vi.hoisted(() => ({
  mockToast: vi.fn(),
  mockNavigate: vi.fn(),
}))

vi.mock('../../services/bank', () => ({
  bankService: {
    listAccounts: vi.fn(),
    syncAccount: vi.fn(),
    syncAllAccounts: vi.fn(),
  },
}))

vi.mock('../../components/Toast', () => ({
  useToast: () => ({ toast: mockToast }),
}))

vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}))

vi.mock('../../services/pushNotifications', () => ({
  notifyHsaReview: vi.fn().mockResolvedValue(undefined),
}))

import { bankService } from '../../services/bank'
import { notifyHsaReview } from '../../services/pushNotifications'

const STORAGE_KEY = 'hsa_last_auto_sync'
const INTERVAL_STORAGE_KEY = 'hsa_sync_interval_ms'
const PUSH_COOLDOWN_KEY = 'hsa_last_push_at'

const staleAccount = {
  id: 'acc-1',
  is_active: true,
  last_synced_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(), // 2 days ago
  institution_name: 'Chase',
  account_name: 'Checking',
}

const freshAccount = {
  id: 'acc-2',
  is_active: true,
  last_synced_at: new Date().toISOString(),
  institution_name: 'BoA',
  account_name: 'HSA',
}

const neverSyncedAccount = {
  id: 'acc-3',
  is_active: true,
  last_synced_at: null,
  institution_name: 'Fidelity',
  account_name: 'Savings',
}

const defaultSyncAllResult = {
  total: 0, succeeded: 0, failed: 0, outcomes: [],
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.removeItem(STORAGE_KEY)
  localStorage.removeItem(INTERVAL_STORAGE_KEY)
  localStorage.removeItem(PUSH_COOLDOWN_KEY)
  ;(bankService.listAccounts as any).mockResolvedValue([])
  ;(bankService.syncAllAccounts as ReturnType<typeof vi.fn>).mockResolvedValue(defaultSyncAllResult)
})

afterEach(() => {
  localStorage.removeItem(STORAGE_KEY)
  localStorage.removeItem(INTERVAL_STORAGE_KEY)
  localStorage.removeItem(PUSH_COOLDOWN_KEY)
})

describe('useAutoSync', () => {
  it('calls sync-all when stale accounts exist', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([staleAccount])
    ;(bankService.syncAllAccounts as any).mockResolvedValue({
      total: 1, succeeded: 1, failed: 0,
      outcomes: [{ account_id: 'acc-1', account_name: 'Checking', status: 'ok', added: 0, skipped: 0 }],
    })

    renderHook(() => useAutoSync())

    await waitFor(() => {
      expect(bankService.syncAllAccounts).toHaveBeenCalled()
    })
  })

  it('calls sync-all when accounts have null last_synced_at', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([neverSyncedAccount])
    ;(bankService.syncAllAccounts as any).mockResolvedValue({
      total: 1, succeeded: 1, failed: 0,
      outcomes: [{ account_id: 'acc-3', account_name: 'Savings', status: 'ok', added: 0, skipped: 0 }],
    })

    renderHook(() => useAutoSync())

    await waitFor(() => {
      expect(bankService.syncAllAccounts).toHaveBeenCalled()
    })
  })

  it('skips sync when all accounts are fresh', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([freshAccount])

    renderHook(() => useAutoSync())

    await waitFor(() => {
      expect(bankService.listAccounts).toHaveBeenCalled()
    })
    expect(bankService.syncAllAccounts).not.toHaveBeenCalled()
  })

  it('skips inactive accounts', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([
      { ...staleAccount, is_active: false },
    ])

    renderHook(() => useAutoSync())

    await waitFor(() => {
      expect(bankService.listAccounts).toHaveBeenCalled()
    })
    expect(bankService.syncAllAccounts).not.toHaveBeenCalled()
  })

  it('does not run again if checked within 24h', async () => {
    localStorage.setItem(STORAGE_KEY, Date.now().toString())
    ;(bankService.listAccounts as any).mockResolvedValue([staleAccount])

    renderHook(() => useAutoSync())

    await new Promise(r => setTimeout(r, 50))
    expect(bankService.listAccounts).not.toHaveBeenCalled()
  })

  it('shows error toast for disconnected accounts', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([staleAccount])
    ;(bankService.syncAllAccounts as any).mockResolvedValue({
      total: 1, succeeded: 0, failed: 1,
      outcomes: [{ account_id: 'acc-1', account_name: 'Checking', status: 'disconnected', error: 'expired' }],
    })

    renderHook(() => useAutoSync())

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        'Checking needs to be reconnected',
        'error',
        expect.objectContaining({ label: 'Go to Bank Accounts' })
      )
    })
  })

  it('shows error toast for failed accounts', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([staleAccount])
    ;(bankService.syncAllAccounts as any).mockResolvedValue({
      total: 1, succeeded: 0, failed: 1,
      outcomes: [{ account_id: 'acc-1', account_name: 'Checking', status: 'error', error: 'timeout' }],
    })

    renderHook(() => useAutoSync())

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        'Checking failed to sync',
        'error',
        expect.objectContaining({ label: 'Go to Bank Accounts' })
      )
    })
  })

  it('navigates to /bank when toast action is clicked', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([staleAccount])
    ;(bankService.syncAllAccounts as any).mockResolvedValue({
      total: 1, succeeded: 0, failed: 1,
      outcomes: [{ account_id: 'acc-1', account_name: 'Checking', status: 'disconnected', error: 'expired' }],
    })

    renderHook(() => useAutoSync())

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalled()
    })

    const action = mockToast.mock.calls[0][2]
    act(() => action.onClick())
    expect(mockNavigate).toHaveBeenCalledWith('/bank')
  })

  it('respects a custom 4h interval stored in localStorage', async () => {
    const fourHoursMs = 4 * 60 * 60 * 1000
    // Last check was 5 hours ago — should run with a 4h interval
    localStorage.setItem(STORAGE_KEY, String(Date.now() - 5 * 60 * 60 * 1000))
    localStorage.setItem(INTERVAL_STORAGE_KEY, String(fourHoursMs))
    ;(bankService.listAccounts as any).mockResolvedValue([freshAccount])

    renderHook(() => useAutoSync())

    await waitFor(() => {
      expect(bankService.listAccounts).toHaveBeenCalled()
    })
  })

  it('skips sync when within custom interval', async () => {
    const eightHoursMs = 8 * 60 * 60 * 1000
    // Last check was 4 hours ago — should NOT run with an 8h interval
    localStorage.setItem(STORAGE_KEY, String(Date.now() - 4 * 60 * 60 * 1000))
    localStorage.setItem(INTERVAL_STORAGE_KEY, String(eightHoursMs))
    ;(bankService.listAccounts as any).mockResolvedValue([staleAccount])

    renderHook(() => useAutoSync())

    await new Promise(r => setTimeout(r, 50))
    expect(bankService.listAccounts).not.toHaveBeenCalled()
  })

  it('calls runSync when SW sends a TRIGGER_SYNC message', async () => {
    // jsdom doesn't provide navigator.serviceWorker; set up a minimal mock
    const listeners: Array<(e: MessageEvent) => void> = []
    const mockSW = {
      addEventListener: vi.fn((_type: string, fn: (e: MessageEvent) => void) => listeners.push(fn)),
      removeEventListener: vi.fn(),
    }
    Object.defineProperty(navigator, 'serviceWorker', {
      value: mockSW,
      configurable: true,
    })

    ;(bankService.listAccounts as any).mockResolvedValue([staleAccount])
    ;(bankService.syncAllAccounts as any).mockResolvedValue({
      total: 1, succeeded: 1, failed: 0,
      outcomes: [{ account_id: 'acc-1', account_name: 'Checking', status: 'ok', added: 0, skipped: 0 }],
    })

    renderHook(() => useAutoSync())

    // Trigger the first mount sync to complete before firing the SW message
    await waitFor(() => expect(bankService.listAccounts).toHaveBeenCalledTimes(1))

    // Reset call count, advance the last-check time so shouldCheck() passes again
    ;(bankService.listAccounts as any).mockClear()
    localStorage.removeItem(STORAGE_KEY)

    const messageEvent = new MessageEvent('message', { data: { type: 'TRIGGER_SYNC' } })
    act(() => {
      listeners.forEach(fn => fn(messageEvent))
    })

    await waitFor(() => {
      expect(bankService.listAccounts).toHaveBeenCalled()
    })

    // Restore
    Object.defineProperty(navigator, 'serviceWorker', { value: undefined, configurable: true })
  })

  it('sends push notification based on added count from sync-all outcomes', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([staleAccount])
    ;(bankService.syncAllAccounts as any).mockResolvedValue({
      total: 2, succeeded: 2, failed: 0,
      outcomes: [
        { account_id: 'acc-1', account_name: 'Checking', status: 'ok', added: 3, skipped: 5 },
        { account_id: 'acc-4', account_name: 'Savings', status: 'ok', added: 2, skipped: 3 },
      ],
    })

    renderHook(() => useAutoSync())

    await waitFor(() => {
      expect(notifyHsaReview).toHaveBeenCalledWith(5)
    })
    expect(notifyHsaReview).toHaveBeenCalledTimes(1)
  })

  it('does not call notifyHsaReview when no transactions added', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([staleAccount])
    ;(bankService.syncAllAccounts as any).mockResolvedValue({
      total: 1, succeeded: 1, failed: 0,
      outcomes: [{ account_id: 'acc-1', account_name: 'Checking', status: 'ok', added: 0, skipped: 5 }],
    })

    renderHook(() => useAutoSync())

    await waitFor(() => expect(bankService.syncAllAccounts).toHaveBeenCalled())
    await new Promise(r => setTimeout(r, 50))
    expect(notifyHsaReview).not.toHaveBeenCalled()
  })

  it('does not call notifyHsaReview when push cooldown is active', async () => {
    localStorage.setItem(PUSH_COOLDOWN_KEY, String(Date.now() - 60 * 60 * 1000)) // 1h ago, within 12h cooldown
    ;(bankService.listAccounts as any).mockResolvedValue([staleAccount])
    ;(bankService.syncAllAccounts as any).mockResolvedValue({
      total: 1, succeeded: 1, failed: 0,
      outcomes: [{ account_id: 'acc-1', account_name: 'Checking', status: 'ok', added: 3, skipped: 0 }],
    })

    renderHook(() => useAutoSync())

    await waitFor(() => expect(bankService.syncAllAccounts).toHaveBeenCalled())
    await new Promise(r => setTimeout(r, 50))
    expect(notifyHsaReview).not.toHaveBeenCalled()
  })

  it('calls notifyHsaReview when push cooldown has expired', async () => {
    localStorage.setItem(PUSH_COOLDOWN_KEY, String(Date.now() - 13 * 60 * 60 * 1000)) // 13h ago, beyond 12h cooldown
    ;(bankService.listAccounts as any).mockResolvedValue([staleAccount])
    ;(bankService.syncAllAccounts as any).mockResolvedValue({
      total: 1, succeeded: 1, failed: 0,
      outcomes: [{ account_id: 'acc-1', account_name: 'Checking', status: 'ok', added: 2, skipped: 0 }],
    })

    renderHook(() => useAutoSync())

    await waitFor(() => {
      expect(notifyHsaReview).toHaveBeenCalledWith(2)
    })
  })
})
