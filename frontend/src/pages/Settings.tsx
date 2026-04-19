import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  isPushSupported,
  getExistingSubscription,
  subscribeToPush,
  saveSubscription,
  removeSubscription,
} from '../services/pushNotifications'
import { registerPeriodicSync } from '../services/periodicSync'
import { householdService, Household } from '../services/household'

type PushState = 'loading' | 'unsupported' | 'denied' | 'not_subscribed' | 'subscribed' | 'error'

const INTERVAL_STORAGE_KEY = 'hsa_sync_interval_ms'
const SYNC_OPTIONS = [
  { label: 'Every 4 hours', value: 4 * 60 * 60 * 1000 },
  { label: 'Every 8 hours', value: 8 * 60 * 60 * 1000 },
  { label: 'Every 12 hours', value: 12 * 60 * 60 * 1000 },
  { label: 'Every 24 hours', value: 24 * 60 * 60 * 1000 },
]
const DEFAULT_INTERVAL = 24 * 60 * 60 * 1000

function getStoredInterval(): number {
  const raw = localStorage.getItem(INTERVAL_STORAGE_KEY)
  if (!raw) return DEFAULT_INTERVAL
  const parsed = parseInt(raw, 10)
  return SYNC_OPTIONS.some(o => o.value === parsed) ? parsed : DEFAULT_INTERVAL
}

export default function Settings() {
  const [pushState, setPushState] = useState<PushState>('loading')
  const [subscription, setSubscription] = useState<PushSubscription | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [household, setHousehold] = useState<Household | null>(null)
  const [strictBusy, setStrictBusy] = useState(false)
  const [syncInterval, setSyncInterval] = useState<number>(getStoredInterval)

  useEffect(() => {
    householdService.getMine().then(setHousehold)
  }, [])

  useEffect(() => {
    registerPeriodicSync(syncInterval)
  }, [])

  function handleSyncIntervalChange(value: number) {
    setSyncInterval(value)
    localStorage.setItem(INTERVAL_STORAGE_KEY, String(value))
    registerPeriodicSync(value)
  }

  async function handleToggleStrict() {
    if (!household) return
    setStrictBusy(true)
    try {
      const updated = await householdService.updateSettings(!household.strict_eligibility)
      setHousehold(updated)
    } finally {
      setStrictBusy(false)
    }
  }

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

      {household?.is_admin && (
        <div className="bg-white rounded-lg border border-gray-200 p-6 mb-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-1">Calculation Settings</h2>
          <p className="text-sm text-gray-500 mb-4">
            Control how HSA spending totals are calculated across your household.
          </p>
          <div className="flex items-start gap-4">
            <button
              type="button"
              role="switch"
              aria-checked={household.strict_eligibility}
              onClick={handleToggleStrict}
              disabled={strictBusy}
              className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-sky-500 disabled:opacity-50 ${
                household.strict_eligibility ? 'bg-sky-600' : 'bg-gray-200'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                  household.strict_eligibility ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
            <div>
              <p className="text-sm font-medium text-gray-800">
                Strict eligibility calculations {household.strict_eligibility ? '(on)' : '(off)'}
              </p>
              <p className="text-xs text-gray-500 mt-0.5">
                When on, HSA totals only count transactions that fall within each member's
                configured coverage window. Unassigned transactions and members with no
                coverage periods are excluded. Turn off to count all HSA-tagged transactions
                regardless of coverage windows.
              </p>
            </div>
          </div>
        </div>
      )}

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

      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-4">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Sync Interval</h2>
        <p className="text-sm text-gray-500 mb-4">
          How often to automatically check for new transactions when you have the app open.
          On supported browsers with the app installed, syncs can also run in the background.
        </p>
        <select
          value={syncInterval}
          onChange={e => handleSyncIntervalChange(Number(e.target.value))}
          className="block w-full max-w-xs rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-sky-500"
        >
          {SYNC_OPTIONS.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
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
