/**
 * Passkey Registration Form - No email, no password!
 *
 * Props (all optional):
 *   inviteToken  — pre-fill the invite token field (read-only when provided)
 *   requirePin   — show the family PIN field (used when arriving via an invite link)
 */

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import passkeyService from '../../services/passkey'

interface Props {
  inviteToken?: string
  requirePin?: boolean
  prefilledDisplayName?: string
}

export default function PasskeyRegisterForm({ inviteToken: propInviteToken, requirePin = false, prefilledDisplayName }: Props) {
  const [username, setUsername] = useState('')
  const [displayName, setDisplayName] = useState(prefilledDisplayName ?? '')
  const [deviceName, setDeviceName] = useState('')
  const [inviteToken, setInviteToken] = useState(propInviteToken ?? '')
  const [familyPin, setFamilyPin] = useState('')
  const [requireInvite, setRequireInvite] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  // When the prop changes (e.g. InvitePage passes a token), keep state in sync
  useEffect(() => {
    if (propInviteToken !== undefined) setInviteToken(propInviteToken)
  }, [propInviteToken])

  useEffect(() => {
    // Only fetch app config when this form is used standalone (no prop token)
    if (propInviteToken !== undefined) return
    passkeyService.getAppConfig().then((cfg) => {
      setRequireInvite(cfg.require_invite)
    }).catch(() => {
      // If config fetch fails, default to open registration
    })
  }, [propInviteToken])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    try {
      if (!passkeyService.isSupported()) {
        setError('Passkeys are not supported in this browser. Please use a modern browser like Chrome, Safari, or Edge.')
        setIsLoading(false)
        return
      }

      await passkeyService.register(
        username,
        displayName,
        deviceName || undefined,
        inviteToken || undefined,
        familyPin || undefined,
      )

      await passkeyService.login(username)
      navigate('/family?setup=1')
    } catch (err: any) {
      console.error('Registration error:', err)
      const message = err.response?.data?.detail || err.message || 'Registration failed'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }

  // Show invite token field only in standalone registration when app requires it.
  // When arriving via an invite URL the token is already captured in state and submitted
  // silently — no need to show or ask the family member to enter anything.
  const showInviteField = requireInvite && propInviteToken === undefined

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
        {showInviteField && (
          <div>
            <label htmlFor="inviteToken" className="block text-sm font-medium text-gray-700 mb-1">
              Invite Token *
            </label>
            <input
              id="inviteToken"
              type="text"
              value={inviteToken}
              onChange={(e) => setInviteToken(e.target.value.trim())}
              required
              disabled={isLoading}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 font-mono disabled:opacity-50"
              placeholder="word-word-word"
            />
            <p className="mt-1 text-sm text-gray-500">Enter the invite token you were given</p>
          </div>
        )}

        {requirePin && (
          <div>
            <label htmlFor="familyPin" className="block text-sm font-medium text-gray-700 mb-1">
              Family PIN *
            </label>
            <input
              id="familyPin"
              type="text"
              value={familyPin}
              onChange={(e) => setFamilyPin(e.target.value.trim())}
              required
              disabled={isLoading}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 disabled:opacity-50 font-mono"
              placeholder="word-word"
            />
            <p className="mt-1 text-sm text-gray-500">
              Ask the person who invited you for the family PIN
            </p>
          </div>
        )}

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
            onChange={(e) => !prefilledDisplayName && setDisplayName(e.target.value)}
            required
            disabled={isLoading}
            readOnly={!!prefilledDisplayName}
            className={`w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 ${prefilledDisplayName ? 'bg-gray-50 text-gray-500 cursor-default' : 'disabled:opacity-50'}`}
            placeholder="John Doe"
          />
          {prefilledDisplayName && (
            <p className="mt-1 text-sm text-gray-500">Pre-filled from your invite</p>
          )}
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
