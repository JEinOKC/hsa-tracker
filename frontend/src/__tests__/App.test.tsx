import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi, describe, it, expect, beforeEach } from 'vitest'

// ── Dependency mocks ──────────────────────────────────────────────────────────

vi.mock('../components/Toast', () => ({
  ToastProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))
vi.mock('../components/UpdatePrompt', () => ({ default: () => null }))
vi.mock('../components/ProtectedRoute', () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))
vi.mock('../hooks/useAutoSync', () => ({ useAutoSync: () => undefined }))
vi.mock('../services/bank', () => ({
  bankService: {
    listAllTransactions: () => Promise.resolve([]),
    listAccounts: () => Promise.resolve([]),
  },
}))
vi.mock('virtual:pwa-register/react', () => ({
  useRegisterSW: () => ({
    needRefresh: [false, vi.fn()],
    offlineReady: [false, vi.fn()],
    updateServiceWorker: vi.fn(),
  }),
}))

// Page components — none needed for this test
vi.mock('../pages/Dashboard', () => ({ default: () => null }))
vi.mock('../pages/Transactions', () => ({ default: () => null }))
vi.mock('../pages/BankAccounts', () => ({ default: () => null }))
vi.mock('../pages/FamilyMembers', () => ({ default: () => null }))
vi.mock('../pages/Login', () => ({ default: () => null }))
vi.mock('../pages/Register', () => ({ default: () => null }))
vi.mock('../pages/InvitePage', () => ({ default: () => null }))
vi.mock('../pages/Settings', () => ({ default: () => null }))
vi.mock('../pages/Rules', () => ({ default: () => null }))
vi.mock('../pages/ReviewQueue', () => ({ default: () => null }))
vi.mock('../pages/Portfolio', () => ({ default: () => null }))

import App from '../App'

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('App — pre-React overlay cleanup', () => {
  beforeEach(() => {
    document.getElementById('sw-update-overlay')?.remove()
  })

  it('removes sw-update-overlay when React mounts successfully', () => {
    const overlay = document.createElement('div')
    overlay.id = 'sw-update-overlay'
    document.body.appendChild(overlay)
    expect(document.getElementById('sw-update-overlay')).not.toBeNull()

    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    )

    expect(document.getElementById('sw-update-overlay')).toBeNull()
  })

  it('does not throw when sw-update-overlay is absent', () => {
    expect(document.getElementById('sw-update-overlay')).toBeNull()
    expect(() =>
      render(
        <MemoryRouter initialEntries={['/']}>
          <App />
        </MemoryRouter>
      )
    ).not.toThrow()
  })
})
