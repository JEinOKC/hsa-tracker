/**
 * Passkey Authentication Service - WebAuthn/Passkey support
 */

import api from './api'

export interface PasskeyRegisterStartRequest {
  username: string
  display_name: string
}

export interface PasskeyRegisterCompleteRequest {
  username: string
  credential: any
  device_name?: string
}

export interface PasskeyLoginStartRequest {
  username: string
}

export interface PasskeyLoginCompleteRequest {
  username: string
  credential: any
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface User {
  id: string
  username: string
  display_name: string
  email?: string
  is_active: boolean
  is_superuser: boolean
  created_at: string
  updated_at: string
}

class PasskeyService {
  /**
   * Check if browser supports WebAuthn
   */
  isSupported(): boolean {
    return window.PublicKeyCredential !== undefined
  }

  /**
   * Start passkey registration - Step 1
   */
  async registerStart(username: string, displayName: string): Promise<any> {
    const response = await api.post('/passkey/register/start', {
      username,
      display_name: displayName,
    })
    return response.data
  }

  /**
   * Complete passkey registration - Step 2
   */
  async registerComplete(
    username: string,
    credential: any,
    deviceName?: string
  ): Promise<User> {
    const response = await api.post<User>('/passkey/register/complete', {
      username,
      credential,
      device_name: deviceName,
    })
    return response.data
  }

  /**
   * Full passkey registration flow
   */
  async register(
    username: string,
    displayName: string,
    deviceName?: string
  ): Promise<User> {
    // Step 1: Get registration options from server
    const { options } = await this.registerStart(username, displayName)

    // Step 2: Create passkey with browser
    const credential = await this.createPasskey(options)

    // Step 3: Send credential to server
    return await this.registerComplete(username, credential, deviceName)
  }

  /**
   * Start passkey login - Step 1
   */
  async loginStart(username: string): Promise<any> {
    const response = await api.post('/passkey/login/start', { username })
    return response.data
  }

  /**
   * Complete passkey login - Step 2
   */
  async loginComplete(username: string, credential: any): Promise<TokenResponse> {
    const response = await api.post<TokenResponse>('/passkey/login/complete', {
      username,
      credential,
    })

    // Store tokens
    localStorage.setItem('access_token', response.data.access_token)
    localStorage.setItem('refresh_token', response.data.refresh_token)

    return response.data
  }

  /**
   * Full passkey login flow
   */
  async login(username: string): Promise<TokenResponse> {
    // Step 1: Get authentication options from server
    const { options } = await this.loginStart(username)

    // Step 2: Authenticate with passkey
    const credential = await this.getPasskey(options)

    // Step 3: Send credential to server
    return await this.loginComplete(username, credential)
  }

  /**
   * Create a new passkey credential (browser WebAuthn API)
   */
  private async createPasskey(options: any): Promise<any> {
    // Convert base64url strings to Uint8Array
    const publicKey = {
      ...options,
      challenge: this.base64urlToBuffer(options.challenge),
      user: {
        ...options.user,
        id: this.base64urlToBuffer(options.user.id),
      },
    }

    // Call WebAuthn API
    const credential = await navigator.credentials.create({ publicKey })

    if (!credential) {
      throw new Error('Failed to create passkey')
    }

    // Convert credential to sendable format
    return this.credentialToJSON(credential)
  }

  /**
   * Get existing passkey credential (browser WebAuthn API)
   */
  private async getPasskey(options: any): Promise<any> {
    // Convert base64url strings to Uint8Array
    const publicKey = {
      ...options,
      challenge: this.base64urlToBuffer(options.challenge),
      allowCredentials: options.allowCredentials?.map((cred: any) => ({
        ...cred,
        id: this.base64urlToBuffer(cred.id),
      })),
    }

    // Call WebAuthn API
    const credential = await navigator.credentials.get({ publicKey })

    if (!credential) {
      throw new Error('Failed to get passkey')
    }

    // Convert credential to sendable format
    return this.credentialToJSON(credential)
  }

  /**
   * Convert base64url string to Uint8Array
   */
  private base64urlToBuffer(base64url: string): Uint8Array {
    // Add padding if needed
    const padding = '='.repeat((4 - (base64url.length % 4)) % 4)
    const base64 = base64url.replace(/-/g, '+').replace(/_/g, '/') + padding

    // Decode base64
    const binary = atob(base64)
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i)
    }
    return bytes
  }

  /**
   * Convert Uint8Array to base64url string
   */
  private bufferToBase64url(buffer: ArrayBuffer): string {
    const bytes = new Uint8Array(buffer)
    let binary = ''
    for (let i = 0; i < bytes.length; i++) {
      binary += String.fromCharCode(bytes[i])
    }
    const base64 = btoa(binary)
    return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '')
  }

  /**
   * Convert WebAuthn credential to JSON format for API
   */
  private credentialToJSON(credential: any): any {
    const response = credential.response

    return {
      id: credential.id,
      rawId: this.bufferToBase64url(credential.rawId),
      type: credential.type,
      response: {
        clientDataJSON: this.bufferToBase64url(response.clientDataJSON),
        attestationObject: response.attestationObject
          ? this.bufferToBase64url(response.attestationObject)
          : undefined,
        authenticatorData: response.authenticatorData
          ? this.bufferToBase64url(response.authenticatorData)
          : undefined,
        signature: response.signature
          ? this.bufferToBase64url(response.signature)
          : undefined,
        userHandle: response.userHandle
          ? this.bufferToBase64url(response.userHandle)
          : undefined,
      },
    }
  }
}

export default new PasskeyService()
