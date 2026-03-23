import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ProtectedRoute from '../ProtectedRoute'

vi.mock('../../services/auth', () => ({
  default: {
    isAuthenticated: vi.fn(),
  },
}))

vi.mock('../../store/authStore', () => ({
  useAuthStore: vi.fn(),
}))

import authService from '../../services/auth'
import { useAuthStore } from '../../store/authStore'

function renderProtectedRoute(children = <div>Protected Content</div>) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route path="/login" element={<div>Login Page</div>} />
          <Route
            path="/*"
            element={<ProtectedRoute>{children}</ProtectedRoute>}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('redirects to /login when not authenticated', () => {
    ;(authService.isAuthenticated as any).mockReturnValue(false)
    ;(useAuthStore as any).mockReturnValue({ user: null, fetchUser: vi.fn() })

    renderProtectedRoute()

    // After redirect, login page is shown and protected content is not
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
  })

  it('shows loading spinner when authenticated but user not loaded', () => {
    const fetchUser = vi.fn()
    ;(authService.isAuthenticated as any).mockReturnValue(true)
    ;(useAuthStore as any).mockReturnValue({ user: null, fetchUser })

    renderProtectedRoute()

    expect(screen.getByText(/loading/i)).toBeInTheDocument()
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
  })

  it('renders children when authenticated and user loaded', () => {
    ;(authService.isAuthenticated as any).mockReturnValue(true)
    ;(useAuthStore as any).mockReturnValue({
      user: { id: '1', username: 'test', display_name: 'Test' },
      fetchUser: vi.fn(),
    })

    renderProtectedRoute()

    expect(screen.getByText('Protected Content')).toBeInTheDocument()
  })
})
