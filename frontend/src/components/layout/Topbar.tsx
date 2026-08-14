import { useQuery } from '@tanstack/react-query'
import { Bell, LogOut, Menu, Moon, Search, Sun } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { useTheme } from '../../hooks/useTheme'
import { initials, timeAgo } from '../../lib/format'
import { dashboardApi } from '../../services/api'
import { Dropdown, DropdownItem } from '../ui/Dropdown'

export function Topbar({ onMenuClick }: { onMenuClick: () => void }) {
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const [search, setSearch] = useState('')

  const { data: dashboard } = useQuery({
    queryKey: ['dashboard'],
    queryFn: dashboardApi.stats,
    enabled: !!user,
    staleTime: 30_000,
  })

  const submitSearch = (event: React.FormEvent) => {
    event.preventDefault()
    navigate(`/contacts?q=${encodeURIComponent(search.trim())}`)
  }

  const notifications = dashboard?.recent_activity ?? []

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-zinc-200 bg-white/90 px-4 backdrop-blur dark:border-zinc-800 dark:bg-zinc-900/90 sm:px-6">
      <button
        onClick={onMenuClick}
        className="rounded-lg p-1.5 text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800 lg:hidden"
        aria-label="Open menu"
      >
        <Menu className="h-5 w-5" />
      </button>

      <form onSubmit={submitSearch} className="relative hidden max-w-md flex-1 sm:block">
        <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-zinc-400" />
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search contacts…"
          className="h-9 w-full rounded-lg border border-zinc-200 bg-zinc-50 pr-3 pl-9 text-sm placeholder:text-zinc-400 focus:border-brand-500 focus:bg-white focus:ring-2 focus:ring-brand-500/30 focus:outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:focus:bg-zinc-900"
        />
      </form>

      <div className="flex-1 sm:hidden" />

      <div className="flex items-center gap-1">
        <button
          onClick={toggleTheme}
          className="rounded-lg p-2 text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-800 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
          aria-label="Toggle theme"
        >
          {theme === 'dark' ? <Sun className="h-4.5 w-4.5" /> : <Moon className="h-4.5 w-4.5" />}
        </button>

        <Dropdown
          trigger={
            <span className="relative block rounded-lg p-2 text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-800 dark:hover:bg-zinc-800 dark:hover:text-zinc-100">
              <Bell className="h-4.5 w-4.5" />
              {notifications.length > 0 && (
                <span className="absolute top-1.5 right-1.5 h-1.5 w-1.5 rounded-full bg-brand-500" />
              )}
            </span>
          }
        >
          {(close) => (
            <div className="max-h-80 w-72 overflow-y-auto">
              <p className="border-b border-zinc-100 px-3.5 py-2 text-xs font-semibold tracking-wide text-zinc-400 uppercase dark:border-zinc-800">
                Recent activity
              </p>
              {notifications.length === 0 && (
                <p className="px-3.5 py-4 text-sm text-zinc-500">No activity yet.</p>
              )}
              {notifications.slice(0, 8).map((activity) => (
                <div key={activity.id} className="px-3.5 py-2.5 hover:bg-zinc-50 dark:hover:bg-zinc-800/60">
                  <p className="text-sm text-zinc-700 capitalize dark:text-zinc-200">
                    {activity.action.replace(/[._]/g, ' ')}
                  </p>
                  <p className="text-xs text-zinc-400">{timeAgo(activity.created_at)}</p>
                </div>
              ))}
              <button
                onClick={() => {
                  close()
                  navigate('/messages')
                }}
                className="w-full border-t border-zinc-100 px-3.5 py-2 text-left text-xs font-medium text-brand-600 hover:bg-zinc-50 dark:border-zinc-800 dark:text-brand-400 dark:hover:bg-zinc-800/60"
              >
                View message logs
              </button>
            </div>
          )}
        </Dropdown>

        <Dropdown
          trigger={
            <span className="flex items-center gap-2 rounded-lg p-1.5 pl-2 hover:bg-zinc-100 dark:hover:bg-zinc-800">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-brand-100 text-xs font-bold text-brand-700 dark:bg-brand-500/20 dark:text-brand-300">
                {initials(user?.name ?? '?')}
              </span>
            </span>
          }
        >
          {(close) => (
            <div>
              <div className="border-b border-zinc-100 px-3.5 py-2.5 dark:border-zinc-800">
                <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{user?.name}</p>
                <p className="truncate text-xs text-zinc-500">{user?.email}</p>
              </div>
              <button
                onClick={() => {
                  close()
                  navigate('/settings')
                }}
                className="block w-full px-3.5 py-2 text-left text-sm text-zinc-700 hover:bg-zinc-50 dark:text-zinc-200 dark:hover:bg-zinc-800"
              >
                Settings
              </button>
              <DropdownItem
                danger
                icon={<LogOut className="h-4 w-4" />}
                onClick={() => {
                  close()
                  logout.mutate()
                }}
              >
                Sign out
              </DropdownItem>
            </div>
          )}
        </Dropdown>
      </div>
    </header>
  )
}
