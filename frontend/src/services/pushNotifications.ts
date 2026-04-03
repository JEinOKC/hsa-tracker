import api from './api'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = window.atob(base64)
  return new Uint8Array([...raw].map(c => c.charCodeAt(0)))
}

export function isPushSupported(): boolean {
  return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
}

export async function getVapidPublicKey(): Promise<string> {
  const res = await fetch(`${API_URL}/push/vapid-public-key`)
  const data = await res.json()
  return data.vapid_public_key as string
}

export async function getExistingSubscription(): Promise<PushSubscription | null> {
  if (!isPushSupported()) return null
  const reg = await navigator.serviceWorker.ready
  return reg.pushManager.getSubscription()
}

export async function subscribeToPush(): Promise<PushSubscription | null> {
  if (!isPushSupported()) return null

  const permission = await Notification.requestPermission()
  if (permission !== 'granted') return null

  const reg = await navigator.serviceWorker.ready
  const vapidPublicKey = await getVapidPublicKey()
  if (!vapidPublicKey) return null

  return reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
  })
}

export async function saveSubscription(sub: PushSubscription): Promise<void> {
  const json = sub.toJSON() as { endpoint: string; keys: { p256dh: string; auth: string } }
  await api.post('/push/subscribe', {
    endpoint: sub.endpoint,
    keys: json.keys,
    user_agent: navigator.userAgent,
  })
}

export async function removeSubscription(sub: PushSubscription): Promise<void> {
  const json = sub.toJSON() as { endpoint: string; keys: { p256dh: string; auth: string } }
  await sub.unsubscribe()
  await api.delete('/push/subscribe', { data: { endpoint: sub.endpoint, keys: json.keys } })
}
