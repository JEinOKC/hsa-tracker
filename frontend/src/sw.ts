/// <reference lib="webworker" />
import { clientsClaim } from 'workbox-core'
import { precacheAndRoute } from 'workbox-precaching'

declare const self: ServiceWorkerGlobalScope

clientsClaim()
precacheAndRoute(self.__WB_MANIFEST)

self.addEventListener('push', (event: PushEvent) => {
  if (!event.data) return
  const data = event.data.json() as { title: string; body: string }
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: '/icons/pwa-192.png',
      badge: '/icons/pwa-192.png',
    })
  )
})

self.addEventListener('notificationclick', (event: NotificationEvent) => {
  event.notification.close()
  event.waitUntil(
    self.clients.matchAll({ type: 'window' }).then(clients => {
      if (clients.length > 0) return clients[0].focus()
      return self.clients.openWindow('/')
    })
  )
})
