/**
 * Passkey Registration Form - No email, no password!
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import passkeyService from '../../services/passkey'
import authService from '../../services/auth'

export default function PasskeyRegisterForm() {
  const [username, setUsername] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [deviceName, setDeviceName] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

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

      // Create account with passkey
      await passkeyService.register(username, displayName, deviceName || undefined)

      // Auto-login after registration
      const tokens = await passkeyService.login(username)

      // Redirect to dashboard
      navigate('/')
    } catch (err: any) {
      console.error('Registration error:', err)
      const message = err.response?.data?.detail || err.message || 'Registration failed'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="bg-sky-50 border border-sky-200 rounded-lg p-4">
        <h3 className="font-semibold text-sky-900 mb-2">🔐 Passwordless Registration</h3>
        <p className="text-sm text-sky-700">
          No email or password required! Your device's biometric authentication (Face ID, Touch ID, or fingerprint)
          will be your secure login method.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="username" className="block text-sm font-medium text-gray-700 mb-1">
            Username *
          </label>
          <input
            id="username"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ''))}
            required
            disabled={isLoading}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 disabled:opacity-50"
            placeholder="johndoe"
            pattern="[a-z0-9_-]+"
            title="Lowercase letters, numbers, hyphens, and underscores only"
          />
          <p className="mt-1 text-sm text-gray-500">
            Choose a unique username (lowercase, numbers, -, _)
          </p>
        </div>

        <div>
          <label htmlFor="displayName" className="block text-sm font-medium text-gray-700 mb-1">
            Full Name *
          </label>
          <input
            id="displayName"
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            required
            disabled={isLoading}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 disabled:opacity-50"
            placeholder="John Doe"
          />
        </div>

        <div>
          <label htmlFor="deviceName" className="block text-sm font-medium text-gray-700 mb-1">
            Device Name (optional)
          </label>
          <input
            id="deviceName"
            type="text"
            value={deviceName}
            onChange={(e) => setDeviceName(e.target.value)}
            disabled={isLoading}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 disabled:opacity-50"
            placeholder="My iPhone"
          />
          <p className="mt-1 text-sm text-gray-500">
            Optional: Name this device for easier management
          </p>
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
          {isLoading ? 'Creating account...' : '🔐 Create Account with Passkey'}
        </button>

        <div className="text-sm text-gray-600 bg-gray-50 rounded-lg p-3">
          <p className="font-medium mb-1">What happens next?</p>
          <ol className="list-decimal list-inside space-y-1 text-xs">
            <li>You'll be prompted to authenticate with Face ID, Touch ID, or fingerprint</li>
            <li>Your passkey will be securely stored on your device</li>
            <li>You can add more devices later for convenient access</li>
            <li>No password to remember or forget!</li>
          </ol>
        </div>
      </form>
    </div>
  )
}
