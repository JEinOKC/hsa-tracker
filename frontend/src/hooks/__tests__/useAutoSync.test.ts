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
  },
}))

vi.mock('../../components/Toast', () => ({
  useToast: () => ({ toast: mockToast }),
}))

vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}))

import { bankService } from '../../services/bank'

const STORAGE_KEY = 'hsa_last_auto_sync'

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

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.removeItem(STORAGE_KEY)
  ;(bankService.listAccounts as any).mockResolvedValue([])
  ;(bankService.syncAccount as any).mockResolvedValue({ added: 0, skipped: 0, account_id: '' })
})

afterEach(() => {
  localStorage.removeItem(STORAGE_KEY)
})

describe('useAutoSync', () => {
  it('syncs stale accounts on mount', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([staleAccount])

    renderHook(() => useAutoSync())

    await waitFor(() => {
      expect(bankService.syncAccount).toHaveBeenCalledWith('acc-1')
    })
  })

  it('syncs accounts with null last_synced_at', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([neverSyncedAccount])

    renderHook(() => useAutoSync())

    await waitFor(() => {
      expect(bankService.syncAccount).toHaveBeenCalledWith('acc-3')
    })
  })

  it('skips fresh accounts', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([freshAccount])

    renderHook(() => useAutoSync())

    await waitFor(() => {
      expect(bankService.listAccounts).toHaveBeenCalled()
    })
    expect(bankService.syncAccount).not.toHaveBeenCalled()
  })

  it('skips inactive accounts', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([
      { ...staleAccount, is_active: false },
    ])

    renderHook(() => useAutoSync())

    await waitFor(() => {
      expect(bankService.listAccounts).toHaveBeenCalled()
    })
    expect(bankService.syncAccount).not.toHaveBeenCalled()
  })

  it('does not run again if checked within 24h', async () => {
    localStorage.setItem(STORAGE_KEY, Date.now().toString())
    ;(bankService.listAccounts as any).mockResolvedValue([staleAccount])

    renderHook(() => useAutoSync())

    await new Promise(r => setTimeout(r, 50))
    expect(bankService.listAccounts).not.toHaveBeenCalled()
  })

  it('shows error toast with action when sync returns 422', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([staleAccount])
    ;(bankService.syncAccount as any).mockRejectedValue({ response: { status: 422 } })

    renderHook(() => useAutoSync())

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        'Chase needs to be reconnected',
        'error',
        expect.objectContaining({ label: 'Go to Bank Accounts' })
      )
    })
  })

  it('shows error toast with action when sync fails with other error', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([staleAccount])
    ;(bankService.syncAccount as any).mockRejectedValue({ response: { status: 500 } })

    renderHook(() => useAutoSync())

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        'Chase failed to sync',
        'error',
        expect.objectContaining({ label: 'Go to Bank Accounts' })
      )
    })
  })

  it('navigates to /bank when toast action is clicked', async () => {
    ;(bankService.listAccounts as any).mockResolvedValue([staleAccount])
    ;(bankService.syncAccount as any).mockRejectedValue({ response: { status: 422 } })

    renderHook(() => useAutoSync())

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalled()
    })

    const action = mockToast.mock.calls[0][2]
    act(() => action.onClick())
    expect(mockNavigate).toHaveBeenCalledWith('/bank')
  })
})
