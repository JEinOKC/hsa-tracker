import { useRegisterSW } from 'virtual:pwa-register/react'

export default function UpdatePrompt() {
  const {
    needRefresh: [needRefresh],
    updateServiceWorker,
  } = useRegisterSW()

  if (!needRefresh) return null

  return (
    <div className="bg-amber-400 text-amber-900 shadow-md">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-10 gap-4">
          <span className="text-sm font-medium">A new version is available.</span>
          <button
            onClick={() => updateServiceWorker(true)}
            className="px-3 py-1 bg-amber-900 text-amber-50 text-sm font-semibold rounded hover:bg-amber-800 transition-colors"
          >
            Reload
          </button>
        </div>
      </div>
    </div>
  )
}
