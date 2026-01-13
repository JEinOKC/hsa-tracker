/**
 * Authentication state management with Zustand
 */

import { create } from 'zustand'
import authService, { User } from '../services/auth'

interface AuthState {
  user: User | null
  isLoading: boolean
  error: string | null

  // Actions
  login: (email: string, password: string) => Promise<void>
  loginWithTOTP: (email: string, password: string, totpCode: string) => Promise<void>
  register: (email: string, password: string, displayName: string) => Promise<void>
  logout: () => Promise<void>
  fetchUser: () => Promise<void>
  clearError: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: false,
  error: null,

  login: async (email: string, password: string) => {
    set({ isLoading: true, error: null })
    try {
      await authService.login({ email, password })
      const user = await authService.getCurrentUser()
      set({ user, isLoading: false })
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Login failed'
      set({ error: message, isLoading: false })
      throw error
    }
  },

  loginWithTOTP: async (email: string, password: string, totpCode: string) => {
    set({ isLoading: true, error: null })
    try {
      await authService.loginWithTOTP(email, password, totpCode)
      const user = await authService.getCurrentUser()
      set({ user, isLoading: false })
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Login failed'
      set({ error: message, isLoading: false })
      throw error
    }
  },

  register: async (email: string, password: string, displayName: string) => {
    set({ isLoading: true, error: null })
    try {
      await authService.register({
        email,
        password,
        display_name: displayName,
      })
      // Auto-login after registration
      await authService.login({ email, password })
      const user = await authService.getCurrentUser()
      set({ user, isLoading: false })
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Registration failed'
      set({ error: message, isLoading: false })
      throw error
    }
  },

  logout: async () => {
    set({ isLoading: true })
    try {
      await authService.logout()
    } finally {
      set({ user: null, isLoading: false, error: null })
    }
  },

  fetchUser: async () => {
    if (!authService.isAuthenticated()) {
      set({ user: null })
      return
    }

    set({ isLoading: true })
    try {
      const user = await authService.getCurrentUser()
      set({ user, isLoading: false })
    } catch (error) {
      // If token is invalid, clear auth state
      set({ user: null, isLoading: false })
    }
  },

  clearError: () => set({ error: null }),
}))
