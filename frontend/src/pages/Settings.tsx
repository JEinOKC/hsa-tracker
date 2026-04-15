import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  isPushSupported,
  getExistingSubscription,
  subscribeToPush,
  saveSubscription,
  removeSubscription,
} from '../services/pushNotifications'

type PushState = 'loading' | 'unsupported' | 'denied' | 'not_subscribed' | 'subscribed' | 'error'

export default function Settings() {
  const [pushState, setPushState] = useState<PushState>('loading')
  const [subscription, setSubscription] = useState<PushSubscription | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!isPushSupported()) {
      setPushState('unsupported')
      return
    }
    if (Notification.permission === 'denied') {
      setPushState('denied')
      return
    }
    getExistingSubscription()
      .then(sub => {
        if (sub) {
          setSubscription(sub)
          setPushState('subscribed')
        } else {
          setPushState('not_subscribed')
        }
      })
      .catch(() => setPushState('not_subscribed'))
  }, [])

  async function handleEnable() {
    setBusy(true)
    setError(null)
    try {
      const sub = await subscribeToPush()
      if (!sub) {
        if (Notification.permission === 'denied') {
          setPushState('denied')
        } else {
          setError('Subscription failed — check browser settings.')
          setPushState('error')
        }
        return
      }
      await saveSubscription(sub)
      setSubscription(sub)
      setPushState('subscribed')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unexpected error')
      setPushState('error')
    } finally {
      setBusy(false)
    }
  }

  async function handleDisable() {
    if (!subscription) return
    setBusy(true)
    setError(null)
    try {
      await removeSubscription(subscription)
      setSubscription(null)
      setPushState('not_subscribed')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unexpected error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-8">Settings</h1>

      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-4">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Transaction Rules</h2>
        <p className="text-sm text-gray-500 mb-4">
          Automatically flag or annotate transactions based on matching conditions.
        </p>
        <Link
          to="/settings/rules"
          className="inline-block px-4 py-2 bg-sky-600 text-white text-sm font-medium rounded-md hover:bg-sky-700"
        >
          Manage Rules
        </Link>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Push Notifications</h2>
        <p className="text-sm text-gray-500 mb-6">
          Receive alerts when new transactions are imported or other activity occurs.
        </p>

        {pushState === 'loading' && (
          <p className="text-sm text-gray-500">Checking notification status…</p>
        )}

        {pushState === 'unsupported' && (
          <p className="text-sm text-amber-600">
            Push notifications are not supported in this browser.
          </p>
        )}

        {pushState === 'denied' && (
          <p className="text-sm text-red-600">
            Notification permission was denied. Enable it in your browser's site settings and reload.
          </p>
        )}

        {(pushState === 'not_subscribed' || pushState === 'error') && (
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <span className="inline-block w-2.5 h-2.5 rounded-full bg-gray-300" />
              <span className="text-sm text-gray-600">Not subscribed</span>
            </div>
            <button
              onClick={handleEnable}
              disabled={busy}
              className="self-start px-4 py-2 bg-sky-600 text-white text-sm font-medium rounded-md hover:bg-sky-700 disabled:opacity-50"
            >
              {busy ? 'Enabling…' : 'Enable Push Notifications'}
            </button>
            {error && <p className="text-sm text-red-600">{error}</p>}
          </div>
        )}

        {pushState === 'subscribed' && (
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <span className="inline-block w-2.5 h-2.5 rounded-full bg-green-500" />
              <span className="text-sm text-gray-700">Subscribed — notifications are enabled</span>
            </div>
            <button
              onClick={handleDisable}
              disabled={busy}
              className="self-start px-4 py-2 bg-gray-100 text-gray-700 text-sm font-medium rounded-md hover:bg-gray-200 disabled:opacity-50"
            >
              {busy ? 'Disabling…' : 'Disable Notifications'}
            </button>
            {error && <p className="text-sm text-red-600">{error}</p>}
          </div>
        )}
      </div>
    </div>
  )
}
