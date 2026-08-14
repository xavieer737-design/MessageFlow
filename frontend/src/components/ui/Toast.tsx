import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react'
import { cn } from '../../lib/cn'

type ToastKind = 'success' | 'error' | 'info'
interface ToastItem {
  id: number
  kind: ToastKind
  message: string
}

interface ToastContextValue {
  toast: (kind: ToastKind, message: string) => void
  success: (message: string) => void
  error: (message: string) => void
  info: (message: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function useToast(): ToastContextValue {
  const value = useContext(ToastContext)
  if (!value) throw new Error('useToast must be used inside <ToastProvider>')
  return value
}

let nextId = 1

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const dismiss = useCallback((id: number) => {
    setToasts((items) => items.filter((item) => item.id !== id))
  }, [])

  const toast = useCallback(
    (kind: ToastKind, message: string) => {
      const id = nextId++
      setToasts((items) => [...items.slice(-3), { id, kind, message }])
      window.setTimeout(() => dismiss(id), 4500)
    },
    [dismiss],
  )

  const value: ToastContextValue = {
    toast,
    success: (m) => toast('success', m),
    error: (m) => toast('error', m),
    info: (m) => toast('info', m),
  }

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-80 flex-col gap-2">
        {toasts.map((item) => (
          <div
            key={item.id}
            className={cn(
              'pointer-events-auto flex items-start gap-3 rounded-lg border bg-white p-3.5 shadow-pop animate-fade-in dark:bg-zinc-900',
              item.kind === 'success' && 'border-emerald-200 dark:border-emerald-500/30',
              item.kind === 'error' && 'border-red-200 dark:border-red-500/30',
              item.kind === 'info' && 'border-zinc-200 dark:border-zinc-700',
            )}
            role="status"
          >
            {item.kind === 'success' && (
              <CheckCircle2 className="mt-0.5 h-4.5 w-4.5 shrink-0 text-emerald-600 dark:text-emerald-400" />
            )}
            {item.kind === 'error' && (
              <AlertCircle className="mt-0.5 h-4.5 w-4.5 shrink-0 text-red-600 dark:text-red-400" />
            )}
            {item.kind === 'info' && (
              <Info className="mt-0.5 h-4.5 w-4.5 shrink-0 text-brand-600 dark:text-brand-400" />
            )}
            <p className="flex-1 text-sm text-zinc-700 dark:text-zinc-200">{item.message}</p>
            <button
              onClick={() => dismiss(item.id)}
              className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
              aria-label="Dismiss"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
