/// <reference lib="webworker" />
import { clientsClaim } from 'workbox-core'
import { precacheAndRoute } from 'workbox-precaching'

declare const self: ServiceWorkerGlobalScope

clientsClaim()
precacheAndRoute(self.__WB_MANIFEST)

self.addEventListener('message', (event: ExtendableMessageEvent) => {
  if (event.data?.type === 'SKIP_WAITING') {
    self.skipWaiting()
  }
})

// Periodic Background Sync — Chrome/Edge + installed PWA only.
// Broadcasts TRIGGER_SYNC to all open app windows; the useAutoSync hook
// picks it up and runs the sync with the user's auth token.
self.addEventListener('periodicsync', (event: any) => {
  if (event.tag !== 'hsa-auto-sync') return
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: false }).then(clients => {
      clients.forEach(c => c.postMessage({ type: 'TRIGGER_SYNC' }))
      // No open windows = no auth token available, skip silently.
    })
  )
})

self.addEventListener('push', (event: PushEvent) => {
  if (!event.data) return
  const data = event.data.json() as { title: string; body: string; url?: string }
  // `actions` is a valid Push API extension not yet reflected in the TS lib types
  const options: NotificationOptions & { actions?: { action: string; title: string }[] } = {
    body: data.body,
    icon: '/icons/pwa-192.png',
    badge: '/icons/pwa-192.png',
    data: { url: data.url ?? '/' },
    actions: [{ action: 'review', title: 'Review' }],
  }
  event.waitUntil(self.registration.showNotification(data.title, options))
})

self.addEventListener('notificationclick', (event: NotificationEvent) => {
  event.notification.close()
  const url = (event.notification.data as any)?.url ?? '/'
  event.waitUntil(
    self.clients.matchAll({ type: 'window' }).then(clients => {
      const existing = clients.find(c => c.url.includes(self.location.origin))
      if (existing) {
        existing.focus()
        existing.navigate(url)
        return
      }
      return self.clients.openWindow(url)
    })
  )
})