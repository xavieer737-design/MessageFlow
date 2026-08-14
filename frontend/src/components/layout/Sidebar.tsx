import { NavLink } from 'react-router-dom'
import {
  ChevronsLeft,
  ChevronsRight,
  ClipboardList,
  FileText,
  LayoutDashboard,
  MessageSquareText,
  PhoneOff,
  ScrollText,
  Send,
  Smartphone,
  Users,
  UsersRound,
  X,
  type LucideIcon,
} from 'lucide-react'
import { cn } from '../../lib/cn'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  end?: boolean
}

const mainNav: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/contacts', label: 'Contacts', icon: Users },
  { to: '/groups', label: 'Groups', icon: UsersRound },
  { to: '/campaigns', label: 'Campaigns', icon: Send },
  { to: '/templates', label: 'Templates', icon: FileText },
  { to: '/devices', label: 'Devices', icon: Smartphone },
  { to: '/messages', label: 'Message Logs', icon: ScrollText },
  { to: '/optouts', label: 'Opt-outs', icon: PhoneOff },
]

const bottomNav: NavItem[] = [{ to: '/settings', label: 'Settings', icon: ClipboardList }]

function NavLinks({
  items,
  collapsed,
  onNavigate,
}: {
  items: NavItem[]
  collapsed: boolean
  onNavigate?: () => void
}) {
  return (
    <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-3">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          onClick={onNavigate}
          title={collapsed ? item.label : undefined}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
              collapsed && 'justify-center px-0',
              isActive
                ? 'bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-400'
                : 'text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100',
            )
          }
        >
          <item.icon className="h-4.5 w-4.5 shrink-0" />
          {!collapsed && <span className="truncate">{item.label}</span>}
        </NavLink>
      ))}
    </nav>
  )
}

export function Sidebar({
  collapsed,
  onToggle,
  mobile,
}: {
  collapsed: boolean
  onToggle: () => void
  mobile?: boolean
}) {
  return (
    <div className="flex h-full flex-col">
      <div className={cn('flex h-14 items-center border-b border-zinc-100 dark:border-zinc-800', collapsed ? 'justify-center px-0' : 'justify-between px-4')}>
        {!collapsed && (
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-600 text-white">
              <MessageSquareText className="h-4 w-4" />
            </div>
            <span className="text-[15px] font-bold tracking-tight">MessageFlow</span>
          </div>
        )}
        {collapsed && (
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-600 text-white">
            <MessageSquareText className="h-4 w-4" />
          </div>
        )}
        {mobile && (
          <button onClick={onToggle} className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800" aria-label="Close menu">
            <X className="h-4.5 w-4.5" />
          </button>
        )}
      </div>

      <NavLinks items={mainNav} collapsed={collapsed} onNavigate={mobile ? onToggle : undefined} />

      <div className="border-t border-zinc-100 dark:border-zinc-800">
        <NavLinks items={bottomNav} collapsed={collapsed} onNavigate={mobile ? onToggle : undefined} />
      </div>

      {!mobile && (
        <button
          onClick={onToggle}
          className="flex items-center justify-center gap-2 border-t border-zinc-100 py-3 text-xs font-medium text-zinc-400 hover:text-zinc-700 dark:border-zinc-800 dark:hover:text-zinc-200"
        >
          {collapsed ? <ChevronsRight className="h-4 w-4" /> : <><ChevronsLeft className="h-4 w-4" /> Collapse</>}
        </button>
      )}
    </div>
  )
}
