/**
 * Landing page for family invite links — /invite/:token
 * Validates the token, then renders the registration form pre-filled.
 */

import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import familyInvitesService, { ValidateInviteResponse } from '../services/familyInvites'
import PasskeyRegisterForm from '../components/auth/PasskeyRegisterForm'

export default function InvitePage() {
  const { token } = useParams<{ token: string }>()
  const [status, setStatus] = useState<'loading' | 'valid' | 'invalid'>('loading')
  const [invite, setInvite] = useState<ValidateInviteResponse | null>(null)

  useEffect(() => {
    if (!token) {
      setStatus('invalid')
      return
    }
    familyInvitesService.validate(token).then((result) => {
      if (result.valid) {
        setInvite(result)
        setStatus('valid')
      } else {
        setStatus('invalid')
      }
    }).catch(() => {
      setStatus('invalid')
    })
  }, [token])

  if (status === 'loading') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">Checking invite link…</p>
      </div>
    )
  }

  if (status === 'invalid') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-sm border border-gray-200 p-8 text-center">
          <div className="text-4xl mb-4">🔗</div>
          <h1 className="text-xl font-bold text-gray-900 mb-2">Invite link invalid or expired</h1>
          <p className="text-gray-500 text-sm mb-6">
            This invite link has already been used, has expired, or doesn't exist.
            Ask the person who invited you to generate a new one.
          </p>
          <Link to="/login" className="text-sky-600 hover:underline text-sm">
            Already have an account? Sign in
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4 py-12">
      <div className="max-w-md w-full">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <img src="/favicon.svg" alt="" className="h-8 w-8" />
            <span className="text-gray-900 font-bold text-xl">HSA Tracker</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">You've been invited</h1>
          <p className="text-gray-500 text-sm mt-1">Create your account to get started</p>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
          <PasskeyRegisterForm
            inviteToken={token}
            requirePin={invite?.require_pin ?? false}
            prefilledDisplayName={invite?.family_member_name ?? undefined}
          />
        </div>

        <p className="text-center text-sm text-gray-500 mt-6">
          Already have an account?{' '}
          <Link to="/login" className="text-sky-600 hover:underline">Sign in</Link>
        </p>
      </div>
    </div>
  )
}
