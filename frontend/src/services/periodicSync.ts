/**
 * Registers the Periodic Background Sync tag with the browser.
 *
 * This is Chrome/Edge + installed PWA only. On unsupported browsers the call
 * silently does nothing — the existing tab-visibility sync in useAutoSync
 * covers those cases.
 */
export async function registerPeriodicSync(intervalMs: number): Promise<void> {
  if (!('serviceWorker' in navigator)) return
  const reg = await navigator.serviceWorker.ready
  if (!('periodicSync' in reg)) return
  try {
    await (reg as any).periodicSync.register('hsa-auto-sync', { minInterval: intervalMs })
  } catch {
    // Not installed as a PWA, or the browser denied the permission — skip silently.
  }
}
