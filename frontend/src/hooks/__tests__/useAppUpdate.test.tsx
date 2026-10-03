import { act, renderHook } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { AppUpdateProvider, useAppUpdate } from '../useAppUpdate'

vi.mock('virtual:pwa-register/react', () => ({
  useRegisterSW: vi.fn(),
}))

import { useRegisterSW } from 'virtual:pwa-register/react'
const mockUseRegisterSW = vi.mocked(useRegisterSW)
const mockUpdateServiceWorker = vi.fn()

function setup(registration: Partial<ServiceWorkerRegistration> | undefined, needRefresh = false) {
  mockUseRegisterSW.mockImplementation(options => {
    options?.onRegisteredSW?.('/sw.js', registration as ServiceWorkerRegistration)
    return {
      needRefresh: [needRefresh, vi.fn()],
      offlineReady: [false, vi.fn()],
      updateServiceWorker: mockUpdateServiceWorker,
    }
  })
  return renderHook(() => useAppUpdate(), { wrapper: AppUpdateProvider })
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useAppUpdate', () => {
  it('reports up to date when the server has no new worker', async () => {
    const { result } = setup({ update: vi.fn().mockResolvedValue(undefined), installing: null, waiting: null })
    await act(() => result.current.checkForUpdate())
    expect(result.current.checkStatus).toBe('up_to_date')
  })

  it('leaves the status idle when a new worker is waiting', async () => {
    const { result } = setup({ update: vi.fn().mockResolvedValue(undefined), installing: null, waiting: {} as ServiceWorker })
    await act(() => result.current.checkForUpdate())
    expect(result.current.checkStatus).toBe('idle')
  })

  it('reports an error when the check fails', async () => {
    const { result } = setup({ update: vi.fn().mockRejectedValue(new Error('offline')) })
    await act(() => result.current.checkForUpdate())
    expect(result.current.checkStatus).toBe('error')
  })

  it('reports unsupported without a service worker registration', async () => {
    const { result } = setup(undefined)
    await act(() => result.current.checkForUpdate())
    expect(result.current.checkStatus).toBe('unsupported')
  })

  it('activates the waiting worker when an update is pending', () => {
    const { result } = setup({ update: vi.fn() }, true)
    act(() => result.current.applyUpdate())
    expect(mockUpdateServiceWorker).toHaveBeenCalledWith(true)
  })
})
