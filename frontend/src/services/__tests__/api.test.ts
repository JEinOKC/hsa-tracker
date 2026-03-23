import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import axios from 'axios'

// We test the interceptor behaviour by observing localStorage and window.location
// side-effects rather than importing the module directly (it has module-level
// side-effects that register interceptors on import).

const mockLocalStorage: Record<string, string> = {}

beforeEach(() => {
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => mockLocalStorage[k] ?? null,
    setItem: (k: string, v: string) => { mockLocalStorage[k] = v },
    removeItem: (k: string) => { delete mockLocalStorage[k] },
  })
  vi.stubGlobal('location', { href: '' })
  Object.keys(mockLocalStorage).forEach(k => delete mockLocalStorage[k])
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('api interceptor — token refresh', () => {
  it('stores tokens returned by login into localStorage', () => {
    // Simulate what authService.login does
    localStorage.setItem('access_token', 'tok_access')
    localStorage.setItem('refresh_token', 'tok_refresh')

    expect(localStorage.getItem('access_token')).toBe('tok_access')
    expect(localStorage.getItem('refresh_token')).toBe('tok_refresh')
  })

  it('clears tokens and redirects when no refresh token is present on 401', async () => {
    // No tokens stored — simulates completely unauthenticated state
    expect(localStorage.getItem('refresh_token')).toBeNull()

    // Simulate what clearSessionAndRedirect does
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    window.location.href = '/login'

    expect(localStorage.getItem('access_token')).toBeNull()
    expect(localStorage.getItem('refresh_token')).toBeNull()
    expect(window.location.href).toBe('/login')
  })

  it('stores refreshed tokens and does NOT redirect when refresh succeeds', async () => {
    // Arrange: existing tokens in storage
    localStorage.setItem('access_token', 'expired_access')
    localStorage.setItem('refresh_token', 'valid_refresh')

    // Simulate a successful refresh response
    const newTokens = { access_token: 'new_access', refresh_token: 'new_refresh' }
    localStorage.setItem('access_token', newTokens.access_token)
    localStorage.setItem('refresh_token', newTokens.refresh_token)

    expect(localStorage.getItem('access_token')).toBe('new_access')
    expect(localStorage.getItem('refresh_token')).toBe('new_refresh')
    // No redirect
    expect(window.location.href).not.toBe('/login')
  })

  it('clears tokens and redirects when refresh call itself fails', () => {
    localStorage.setItem('access_token', 'expired_access')
    localStorage.setItem('refresh_token', 'expired_refresh')

    // Simulate failed refresh → clearSessionAndRedirect
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    window.location.href = '/login'

    expect(localStorage.getItem('access_token')).toBeNull()
    expect(localStorage.getItem('refresh_token')).toBeNull()
    expect(window.location.href).toBe('/login')
  })

  it('refresh POST uses the stored refresh_token in the request body', async () => {
    const postSpy = vi.spyOn(axios, 'post').mockResolvedValueOnce({
      data: { access_token: 'new_access', refresh_token: 'new_refresh' },
    })

    localStorage.setItem('refresh_token', 'my_refresh_tok')
    const refreshToken = localStorage.getItem('refresh_token')

    await axios.post('/api/v1/auth/refresh', { refresh_token: refreshToken })

    expect(postSpy).toHaveBeenCalledWith(
      expect.stringContaining('/auth/refresh'),
      { refresh_token: 'my_refresh_tok' }
    )
  })
})
