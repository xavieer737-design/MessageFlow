import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'
import { cn } from '../../lib/cn'

export function AppLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
      {/* Desktop sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-30 hidden border-r border-zinc-200 bg-white transition-all duration-200 dark:border-zinc-800 dark:bg-zinc-900 lg:block',
          collapsed ? 'w-16' : 'w-60',
        )}
      >
        <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((value) => !value)} />
      </aside>

      {/* Mobile sidebar */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-zinc-950/40" onClick={() => setMobileOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 border-r border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
            <Sidebar collapsed={false} onToggle={() => setMobileOpen(false)} mobile />
          </aside>
        </div>
      )}

      <div className={cn('flex min-h-screen flex-col transition-all duration-200', collapsed ? 'lg:pl-16' : 'lg:pl-60')}>
        <Topbar onMenuClick={() => setMobileOpen(true)} />
        <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <Outlet />
        </main>
        <footer className="border-t border-zinc-200 px-6 py-4 text-xs text-zinc-400 dark:border-zinc-800 dark:text-zinc-500">
          MessageFlow · Phase 1 prepares campaigns; no SMS is sent without a connected device.
        </footer>
      </div>
    </div>
  )
}
