/**
 * Login Form Component
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'

export default function LoginForm() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [totpCode, setTotpCode] = useState('')
  const [showTOTP, setShowTOTP] = useState(false)
  const navigate = useNavigate()

  const { login, loginWithTOTP, isLoading, error, clearError } = useAuthStore()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    clearError()

    try {
      if (showTOTP) {
        await loginWithTOTP(email, password, totpCode)
      } else {
        await login(email, password)
      }
      // Redirect to dashboard on success
      navigate('/')
    } catch (err: any) {
      // Check if TOTP is required
      if (err.response?.headers?.['x-totp-required'] === 'true') {
        setShowTOTP(true)
      }
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
          Email
        </label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          disabled={isLoading}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
          placeholder="you@example.com"
        />
      </div>

      <div>
        <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
          Password
        </label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          disabled={isLoading}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
          placeholder="••••••••"
        />
      </div>

      {showTOTP && (
        <div>
          <label htmlFor="totpCode" className="block text-sm font-medium text-gray-700 mb-1">
            2FA Code
          </label>
          <input
            id="totpCode"
            type="text"
            value={totpCode}
            onChange={(e) => setTotpCode(e.target.value)}
            required
            disabled={isLoading}
            maxLength={6}
            pattern="[0-9]{6}"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            placeholder="123456"
          />
          <p className="mt-1 text-sm text-gray-500">
            Enter the 6-digit code from your authenticator app
          </p>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={isLoading}
        className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-medium py-2 px-4 rounded-lg transition-colors"
      >
        {isLoading ? 'Signing in...' : 'Sign In'}
      </button>

      {showTOTP && (
        <button
          type="button"
          onClick={() => setShowTOTP(false)}
          className="w-full text-sm text-gray-600 hover:text-gray-800"
        >
          ← Back to password login
        </button>
      )}
    </form>
  )
}
