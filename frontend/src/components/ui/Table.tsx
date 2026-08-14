import type { ReactNode } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '../../lib/cn'

export function Table({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('overflow-x-auto', className)}>
      <table className="w-full min-w-[720px] border-collapse text-sm">{children}</table>
    </div>
  )
}

export function THead({ children }: { children: ReactNode }) {
  return (
    <thead>
      <tr className="border-b border-zinc-200 bg-zinc-50/80 dark:border-zinc-800 dark:bg-zinc-800/40">
        {children}
      </tr>
    </thead>
  )
}

export function Th({
  children,
  className,
  onClick,
  active,
  direction,
}: {
  children?: ReactNode
  className?: string
  onClick?: () => void
  active?: boolean
  direction?: 'asc' | 'desc'
}) {
  return (
    <th
      onClick={onClick}
      className={cn(
        'px-4 py-2.5 text-left text-xs font-semibold tracking-wide text-zinc-500 uppercase dark:text-zinc-400',
        onClick && 'cursor-pointer select-none hover:text-zinc-800 dark:hover:text-zinc-200',
        className,
      )}
    >
      {children}
      {active && <span className="ml-1 text-brand-600 dark:text-brand-400">{direction === 'asc' ? '↑' : '↓'}</span>}
    </th>
  )
}

export function Td({
  children,
  className,
  colSpan,
}: {
  children?: ReactNode
  className?: string
  colSpan?: number
}) {
  return (
    <td colSpan={colSpan} className={cn('px-4 py-3 align-middle text-zinc-700 dark:text-zinc-300', className)}>
      {children}
    </td>
  )
}

export function TRow({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <tr
      className={cn(
        'border-b border-zinc-100 transition-colors last:border-0 hover:bg-zinc-50/70 dark:border-zinc-800/70 dark:hover:bg-zinc-800/30',
        className,
      )}
    >
      {children}
    </tr>
  )
}

export function Pagination({
  page,
  pages,
  total,
  onChange,
}: {
  page: number
  pages: number
  total: number
  onChange: (page: number) => void
}) {
  if (pages <= 1) return null
  return (
    <div className="flex items-center justify-between border-t border-zinc-100 px-5 py-3 dark:border-zinc-800">
      <p className="text-xs text-zinc-500 dark:text-zinc-400">
        {total} result{total === 1 ? '' : 's'} · page {page} of {pages}
      </p>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onChange(page - 1)}
          disabled={page <= 1}
          className="rounded-lg p-1.5 text-zinc-500 hover:bg-zinc-100 disabled:opacity-40 dark:hover:bg-zinc-800"
          aria-label="Previous page"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <span className="px-2 text-xs font-medium text-zinc-600 dark:text-zinc-300">
          {page} / {pages}
        </span>
        <button
          onClick={() => onChange(page + 1)}
          disabled={page >= pages}
          className="rounded-lg p-1.5 text-zinc-500 hover:bg-zinc-100 disabled:opacity-40 dark:hover:bg-zinc-800"
          aria-label="Next page"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
