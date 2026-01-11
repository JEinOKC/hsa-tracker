/**
 * Authentication API service
 */

import api from './api'

export interface RegisterData {
  email: string
  password: string
  display_name: string
}

export interface LoginData {
  email: string
  password: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface User {
  id: string
  email: string
  display_name: string
  is_active: boolean
  is_superuser: boolean
  created_at: string
  updated_at: string
}

export interface TOTPSetupResponse {
  secret: string
  qr_code_url: string
  backup_codes: string[]
}

export interface SecurityInfo {
  has_password: boolean
  has_totp: boolean
  totp_verified: boolean
  passkey_count: number
  backup_codes_remaining: number
}

class AuthService {
  /**
   * Register a new user
   */
  async register(data: RegisterData): Promise<User> {
    const response = await api.post<User>('/auth/register', data)
    return response.data
  }

  /**
   * Login with email and password
   */
  async login(data: LoginData): Promise<TokenResponse> {
    const response = await api.post<TokenResponse>('/auth/login', data)

    // Store tokens
    localStorage.setItem('access_token', response.data.access_token)
    localStorage.setItem('refresh_token', response.data.refresh_token)

    return response.data
  }

  /**
   * Login with TOTP code
   */
  async loginWithTOTP(
    email: string,
    password: string,
    totpCode: string
  ): Promise<TokenResponse> {
    const response = await api.post<TokenResponse>('/auth/totp/login', null, {
      params: {
        email,
        password,
        totp_code: totpCode,
      },
    })

    // Store tokens
    localStorage.setItem('access_token', response.data.access_token)
    localStorage.setItem('refresh_token', response.data.refresh_token)

    return response.data
  }

  /**
   * Login with backup code
   */
  async loginWithBackupCode(
    email: string,
    password: string,
    backupCode: string
  ): Promise<TokenResponse> {
    const response = await api.post<TokenResponse>('/auth/backup-code/verify', null, {
      params: {
        email,
        password,
        backup_code: backupCode,
      },
    })

    // Store tokens
    localStorage.setItem('access_token', response.data.access_token)
    localStorage.setItem('refresh_token', response.data.refresh_token)

    return response.data
  }

  /**
   * Logout current user
   */
  async logout(): Promise<void> {
    try {
      await api.post('/auth/logout')
    } finally {
      // Clear tokens regardless of API response
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
    }
  }

  /**
   * Get current user info
   */
  async getCurrentUser(): Promise<User> {
    const response = await api.get<User>('/auth/me')
    return response.data
  }

  /**
   * Change password
   */
  async changePassword(currentPassword: string, newPassword: string): Promise<void> {
    await api.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
  }

  /**
   * Set up TOTP (2FA)
   */
  async setupTOTP(): Promise<TOTPSetupResponse> {
    const response = await api.post<TOTPSetupResponse>('/auth/totp/setup')
    return response.data
  }

  /**
   * Verify TOTP code to activate 2FA
   */
  async verifyTOTP(code: string): Promise<void> {
    await api.post('/auth/totp/verify', { code })
  }

  /**
   * Disable TOTP (2FA)
   */
  async disableTOTP(password: string): Promise<void> {
    await api.post('/auth/totp/disable', null, {
      params: { password },
    })
  }

  /**
   * Get account security info
   */
  async getSecurityInfo(): Promise<SecurityInfo> {
    const response = await api.get<SecurityInfo>('/auth/security-info')
    return response.data
  }

  /**
   * Check if user is authenticated
   */
  isAuthenticated(): boolean {
    return !!localStorage.getItem('access_token')
  }

  /**
   * Get stored access token
   */
  getAccessToken(): string | null {
    return localStorage.getItem('access_token')
  }
}

export default new AuthService()
