import { createContext, useContext, useState, useCallback, useRef } from 'react'
import { XIcon } from './icons'

export type ToastType = 'success' | 'error'

export interface ToastAction {
  label: string
  onClick: () => void
}

interface ToastItem {
  id: number
  message: string
  type: ToastType
  action?: ToastAction
}

interface ToastContextValue {
  toast: (message: string, type?: ToastType, action?: ToastAction) => void
}

const ToastContext = createContext<ToastContextValue>({ toast: () => {} })

const DISMISS_MS = 6000

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const nextId = useRef(0)

  const toast = useCallback((message: string, type: ToastType = 'success', action?: ToastAction) => {
    const id = ++nextId.current
    setToasts(prev => [...prev, { id, message, type, action }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), DISMISS_MS)
  }, [])

  const dismiss = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      {/*
        Anchored to the bottom so toasts never cover the header's refresh
        button.  On mobile they sit above the fixed tab bar; from md up the
        tab bar is hidden, so they drop to the bottom edge.
      */}
      <div
        role="region"
        aria-label="Notifications"
        className="fixed left-4 right-4 sm:left-auto sm:right-4 sm:w-80 z-[60] flex flex-col gap-2 pointer-events-none bottom-[calc(4.25rem+max(env(safe-area-inset-bottom),0.75rem))] md:bottom-[calc(1rem+env(safe-area-inset-bottom,0px))]"
      >
        {toasts.map(t => (
          <div
            key={t.id}
            role="alert"
            className={`flex items-start gap-3 px-4 py-3 rounded-lg shadow-lg pointer-events-auto text-sm font-medium animate-fade-in ${
              t.type === 'error' ? 'bg-red-600 text-white' : 'bg-gray-900 text-white'
            }`}
          >
            <span className="flex-1">
              {t.message}
              {t.action && (
                <button
                  onClick={() => { t.action!.onClick(); dismiss(t.id) }}
                  className="block mt-1 underline opacity-90 hover:opacity-100 text-left"
                >
                  {t.action.label}
                </button>
              )}
            </span>
            <button
              onClick={() => dismiss(t.id)}
              aria-label="Dismiss"
              className="shrink-0 opacity-60 hover:opacity-100 transition-opacity"
            >
              <XIcon className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  return useContext(ToastContext)
}
