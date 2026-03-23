import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../api', () => ({
  default: { post: vi.fn() },
}))

import api from '../api'
import passkeyService from '../passkey'

describe('PasskeyService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  describe('isSupported', () => {
    it('returns true when PublicKeyCredential exists', () => {
      expect(passkeyService.isSupported()).toBe(true)
    })

    it('returns false when PublicKeyCredential is undefined', () => {
      const original = window.PublicKeyCredential
      // @ts-ignore
      delete window.PublicKeyCredential
      expect(passkeyService.isSupported()).toBe(false)
      Object.defineProperty(window, 'PublicKeyCredential', {
        value: original,
        writable: true,
        configurable: true,
      })
    })
  })

  describe('registerStart', () => {
    it('calls API with correct payload', async () => {
      ;(api.post as any).mockResolvedValue({ data: { options: {}, username: 'testuser' } })
      await passkeyService.registerStart('testuser', 'Test User')
      expect(api.post).toHaveBeenCalledWith('/passkey/register/start', {
        username: 'testuser',
        display_name: 'Test User',
      })
    })

    it('returns server response data', async () => {
      const mockData = { options: { challenge: 'abc' }, username: 'testuser' }
      ;(api.post as any).mockResolvedValue({ data: mockData })
      const result = await passkeyService.registerStart('testuser', 'Test User')
      expect(result).toEqual(mockData)
    })
  })

  describe('loginStart', () => {
    it('calls API with username', async () => {
      ;(api.post as any).mockResolvedValue({ data: { options: {} } })
      await passkeyService.loginStart('testuser')
      expect(api.post).toHaveBeenCalledWith('/passkey/login/start', {
        username: 'testuser',
      })
    })
  })

  describe('loginComplete', () => {
    it('stores tokens in localStorage', async () => {
      ;(api.post as any).mockResolvedValue({
        data: { access_token: 'at-123', refresh_token: 'rt-456', token_type: 'bearer' },
      })
      await passkeyService.loginComplete('testuser', { id: 'cred' })
      expect(localStorage.getItem('access_token')).toBe('at-123')
      expect(localStorage.getItem('refresh_token')).toBe('rt-456')
    })

    it('returns token response', async () => {
      const tokenData = { access_token: 'at', refresh_token: 'rt', token_type: 'bearer' }
      ;(api.post as any).mockResolvedValue({ data: tokenData })
      const result = await passkeyService.loginComplete('testuser', { id: 'cred' })
      expect(result).toEqual(tokenData)
    })
  })
})
