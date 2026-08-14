import { useEffect, useRef, useState, type ReactNode } from 'react'
import { MoreHorizontal } from 'lucide-react'
import { cn } from '../../lib/cn'

export function Dropdown({
  trigger,
  children,
  align = 'right',
  triggerClassName,
}: {
  trigger?: ReactNode
  children: ReactNode | ((close: () => void) => ReactNode)
  align?: 'left' | 'right'
  triggerClassName?: string
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false)
    }
    const keyHandler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    document.addEventListener('keydown', keyHandler)
    return () => {
      document.removeEventListener('mousedown', handler)
      document.removeEventListener('keydown', keyHandler)
    }
  }, [open])

  const close = () => setOpen(false)

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((value) => !value)}
        className={cn(
          'rounded-lg p-1.5 text-zinc-400 transition-colors hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200',
          triggerClassName,
        )}
        aria-label="More actions"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        {trigger ?? <MoreHorizontal className="h-4.5 w-4.5" />}
      </button>
      {open && (
        <div
          className={cn(
            'absolute z-40 mt-1 min-w-[180px] rounded-lg border border-zinc-200 bg-white py-1 shadow-pop animate-scale-in dark:border-zinc-700 dark:bg-zinc-900',
            align === 'right' ? 'right-0' : 'left-0',
          )}
          role="menu"
        >
          {typeof children === 'function' ? children(close) : children}
        </div>
      )}
    </div>
  )
}

export function DropdownItem({
  onClick,
  children,
  danger,
  icon,
}: {
  onClick?: () => void
  children: ReactNode
  danger?: boolean
  icon?: ReactNode
}) {
  return (
    <button
      role="menuitem"
      onClick={onClick}
      className={cn(
        'flex w-full items-center gap-2.5 px-3.5 py-2 text-left text-sm transition-colors',
        danger
          ? 'text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/10'
          : 'text-zinc-700 hover:bg-zinc-50 dark:text-zinc-200 dark:hover:bg-zinc-800',
      )}
    >
      {icon}
      {children}
    </button>
  )
}
