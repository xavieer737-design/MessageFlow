import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

type Tone = 'gray' | 'green' | 'red' | 'amber' | 'blue' | 'violet' | 'zinc'

const tones: Record<Tone, string> = {
  gray: 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300',
  zinc: 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-200',
  green: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400',
  red: 'bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-400',
  amber: 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400',
  blue: 'bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:text-blue-400',
  violet: 'bg-violet-50 text-violet-700 dark:bg-violet-500/10 dark:text-violet-400',
}

export function Badge({
  tone = 'gray',
  children,
  className,
}: {
  tone?: Tone
  children: ReactNode
  className?: string
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap',
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}

const statusTones: Record<string, Tone> = {
  DRAFT: 'gray',
  READY: 'blue',
  SCHEDULED: 'violet',
  RUNNING: 'green',
  PAUSED: 'amber',
  COMPLETED: 'green',
  CANCELLED: 'red',
  PENDING: 'gray',
  QUEUED: 'blue',
  SENT: 'green',
  FAILED: 'red',
  SKIPPED: 'amber',
  OPTED_OUT: 'red',
  CONNECTED: 'green',
  DISCONNECTED: 'gray',
  CONNECTING: 'blue',
  OFFLINE: 'amber',
  ERROR: 'red',
}

export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={statusTones[status] ?? 'gray'}>{status.replace('_', ' ')}</Badge>
}
