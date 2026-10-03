import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { useRegisterSW } from 'virtual:pwa-register/react'

// How often an open app asks the server for a new service worker. Without
// this, iOS only checks when the app is cold-launched.
const UPDATE_CHECK_INTERVAL_MS = 60 * 60 * 1000

export type UpdateCheckStatus = 'idle' | 'checking' | 'up_to_date' | 'unsupported' | 'error'

interface AppUpdateValue {
  needRefresh: boolean
  checkStatus: UpdateCheckStatus
  checkForUpdate: () => Promise<void>
  applyUpdate: () => void
}

// Default lets components render outside the provider (e.g. in isolated tests).
const AppUpdateContext = createContext<AppUpdateValue>({
  needRefresh: false,
  checkStatus: 'unsupported',
  checkForUpdate: async () => {},
  applyUpdate: () => window.location.reload(),
})

/** Waits for a freshly found worker to finish installing (or fail). */
function waitForInstall(worker: ServiceWorker): Promise<void> {
  return new Promise(resolve => {
    if (worker.state !== 'installing') return resolve()
    worker.addEventListener('statechange', () => {
      if (worker.state !== 'installing') resolve()
    })
  })
}

/** Owns the single service-worker registration; banner and Settings share it. */
export function AppUpdateProvider({ children }: { children: React.ReactNode }) {
  const registrationRef = useRef<ServiceWorkerRegistration | null>(null)
  const [checkStatus, setCheckStatus] = useState<UpdateCheckStatus>('idle')

  const {
    needRefresh: [needRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegisteredSW(_url, registration) {
      registrationRef.current = registration ?? null
    },
  })

  useEffect(() => {
    const check = () => { registrationRef.current?.update().catch(() => {}) }
    const onVisible = () => { if (document.visibilityState === 'visible') check() }
    const interval = setInterval(check, UPDATE_CHECK_INTERVAL_MS)
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      clearInterval(interval)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [])

  const checkForUpdate = useCallback(async () => {
    const registration = registrationRef.current
    if (!registration) {
      setCheckStatus('unsupported')
      return
    }
    setCheckStatus('checking')
    try {
      await registration.update()
      if (registration.installing) await waitForInstall(registration.installing)
      // A waiting worker flips needRefresh via the plugin's own listener.
      setCheckStatus(registration.waiting ? 'idle' : 'up_to_date')
    } catch {
      setCheckStatus('error')
    }
  }, [])

  const applyUpdate = useCallback(() => {
    if (needRefresh) updateServiceWorker(true)
    else window.location.reload()
  }, [needRefresh, updateServiceWorker])

  return (
    <AppUpdateContext.Provider value={{ needRefresh, checkStatus, checkForUpdate, applyUpdate }}>
      {children}
    </AppUpdateContext.Provider>
  )
}

export function useAppUpdate() {
  return useContext(AppUpdateContext)
}
