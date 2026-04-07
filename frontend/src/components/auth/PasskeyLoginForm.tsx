/**
 * Passkey Login Form - Passwordless authentication
 */

import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import passkeyService from '../../services/passkey'

export default function PasskeyLoginForm() {
  const [username, setUsername] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const location = useLocation()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    try {
      // Check if passkeys are supported
      if (!passkeyService.isSupported()) {
        setError('Passkeys are not supported in this browser. Please use a modern browser like Chrome, Safari, or Edge.')
        setIsLoading(false)
        return
      }

      // Login with passkey
      await passkeyService.login(username)

      // Redirect to original destination or dashboard
      const from = (location.state as any)?.from?.pathname || '/'
      navigate(from, { replace: true })
    } catch (err: any) {
      console.error('Login error:', err)
      const message = err.response?.data?.detail || err.message || 'Login failed'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="bg-sky-50 border border-sky-200 rounded-lg p-4">
        <h3 className="font-semibold text-sky-900 mb-2">🔐 Passwordless Login</h3>
        <p className="text-sm text-sky-700">
          Login securely with your device's biometric authentication. No password needed!
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="username" className="block text-sm font-medium text-gray-700 mb-1">
            Username
          </label>
          <input
            id="username"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value.toLowerCase())}
            required
            disabled={isLoading}
            autoFocus
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 disabled:opacity-50"
            placeholder="johndoe"
          />
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={isLoading}
          className="w-full bg-sky-600 hover:bg-sky-700 disabled:bg-sky-300 text-white font-medium py-2 px-4 rounded-lg transition-colors"
        >
          {isLoading ? 'Authenticating...' : '🔐 Login with Passkey'}
        </button>

        <div className="text-sm text-gray-600 bg-gray-50 rounded-lg p-3">
          <p className="font-medium mb-1">What happens next?</p>
          <p className="text-xs">
            You'll be prompted to authenticate with Face ID, Touch ID, fingerprint, or your device's PIN.
            Your passkey never leaves your device!
          </p>
        </div>
      </form>
    </div>
  )
}
