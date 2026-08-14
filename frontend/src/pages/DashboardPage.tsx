import { useQuery } from '@tanstack/react-query'
import {
  AlertTriangle,
  ArrowRight,
  PhoneOff,
  Send,
  Smartphone,
  Users,
  XCircle,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { Spinner, PageHeader } from '../components/ui/Misc'
import { StatusBadge } from '../components/ui/Badge'
import { formatNumber, timeAgo } from '../lib/format'
import { dashboardApi } from '../services/api'
import type { CampaignStatus } from '../types'

const activityLabels: Record<string, string> = {
  'auth.register': 'Registered account',
  'auth.login': 'Signed in',
  'contact.created': 'Added contact',
  'contact.updated': 'Updated contact',
  'contact.deleted': 'Deleted contact',
  'contact.imported': 'Imported contacts',
  'group.created': 'Created group',
  'template.created': 'Created template',
  'campaign.created': 'Created campaign',
  'campaign.validated': 'Validated campaign',
  'campaign.ready': 'Campaign ready',
  'campaign.duplicated': 'Duplicated campaign',
  'campaign.paused': 'Paused campaign',
  'campaign.resumed': 'Resumed campaign',
  'campaign.cancelled': 'Cancelled campaign',
  'optout.created': 'Added opt-out',
  'device.registered': 'Registered device',
}

export function DashboardPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['dashboard'],
    queryFn: dashboardApi.stats,
  })

  if (isLoading) {
    return (
      <div className="flex justify-center py-24">
        <Spinner className="h-7 w-7" />
      </div>
    )
  }

  if (isError || !data) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title="Could not load the dashboard"
        description="The backend may be unavailable. Check that the API server is running."
      />
    )
  }

  const stats = [
    {
      label: 'Total Contacts',
      value: data.stats.total_contacts,
      icon: Users,
      tone: 'text-brand-600 bg-brand-50 dark:text-brand-400 dark:bg-brand-500/10',
    },
    {
      label: 'Active Campaigns',
      value: data.stats.active_campaigns,
      icon: Send,
      tone: 'text-blue-600 bg-blue-50 dark:text-blue-400 dark:bg-blue-500/10',
    },
    {
      label: 'Messages Sent',
      value: data.stats.messages_sent,
      icon: Send,
      tone: 'text-emerald-600 bg-emerald-50 dark:text-emerald-400 dark:bg-emerald-500/10',
    },
    {
      label: 'Failed Messages',
      value: data.stats.failed_messages,
      icon: XCircle,
      tone: 'text-red-600 bg-red-50 dark:text-red-400 dark:bg-red-500/10',
    },
    {
      label: 'Opt-outs',
      value: data.stats.opt_outs,
      icon: PhoneOff,
      tone: 'text-amber-600 bg-amber-50 dark:text-amber-400 dark:bg-amber-500/10',
    },
    {
      label: 'Connected Devices',
      value: data.stats.connected_devices,
      icon: Smartphone,
      tone: 'text-violet-600 bg-violet-50 dark:text-violet-400 dark:bg-violet-500/10',
    },
  ]

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Dashboard"
        description="A live view of your messaging workspace. Nothing is sent until a device is connected."
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
        {stats.map((stat) => (
          <Card key={stat.label} className="p-4">
            <div className="flex items-center gap-3">
              <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${stat.tone}`}>
                <stat.icon className="h-4.5 w-4.5" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-xs font-medium text-zinc-500 dark:text-zinc-400">{stat.label}</p>
                <p className="text-xl font-bold text-zinc-900 dark:text-zinc-50">{formatNumber(stat.value)}</p>
              </div>
            </div>
          </Card>
        ))}
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader
            title="Recent Campaigns"
            description="Your latest campaigns and their real statuses"
            actions={
              <Link to="/campaigns" className="inline-flex items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400">
                View all <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            }
          />
          {data.recent_campaigns.length === 0 ? (
            <EmptyState
              icon={Send}
              title="No campaigns yet"
              description="Create your first campaign to start preparing personalized messages."
              action={
                <Link to="/campaigns/new" className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
                  New campaign
                </Link>
              }
            />
          ) : (
            <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {data.recent_campaigns.map((campaign) => (
                <Link
                  key={campaign.id}
                  to={`/campaigns/${campaign.id}`}
                  className="flex items-center justify-between gap-4 px-5 py-3.5 transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/40"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-zinc-900 dark:text-zinc-100">{campaign.name}</p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">
                      {formatNumber(campaign.recipient_count)} recipients · created {timeAgo(campaign.created_at)}
                    </p>
                  </div>
                  <StatusBadge status={campaign.status as CampaignStatus} />
                </Link>
              ))}
            </div>
          )}
        </Card>

        <Card>
          <CardHeader title="Device Status" description="Android devices for future sending" />
          {data.devices.length === 0 ? (
            <EmptyState
              icon={Smartphone}
              title="No Android device connected"
              description="Connect an Android phone to start sending messages."
              action={
                <Link to="/devices" className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
                  Connect Android Device
                </Link>
              }
            />
          ) : (
            <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {data.devices.map((device) => (
                <div key={device.id} className="flex items-center justify-between px-5 py-3.5">
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-zinc-100 text-zinc-500 dark:bg-zinc-800">
                      <Smartphone className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">{device.device_name}</p>
                      <p className="text-xs text-zinc-500">Last seen {timeAgo(device.last_seen)}</p>
                    </div>
                  </div>
                  <StatusBadge status={device.connection_status} />
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader
          title="Recent Activity"
          description="Audit trail of real actions in your workspace"
          actions={
            <Link to="/messages" className="inline-flex items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400">
              Message logs <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          }
        />
        {data.recent_activity.length === 0 ? (
          <EmptyState title="No activity yet" description="Actions like imports and campaign validation will appear here." />
        ) : (
          <div className="grid grid-cols-1 divide-y divide-zinc-100 sm:grid-cols-2 sm:divide-x sm:divide-y-0 dark:divide-zinc-800">
            {data.recent_activity.map((activity) => (
              <div key={activity.id} className="flex items-center justify-between gap-4 px-5 py-3">
                <p className="text-sm text-zinc-700 dark:text-zinc-300">
                  {activityLabels[activity.action] ?? activity.action.replace(/[._]/g, ' ')}
                </p>
                <p className="shrink-0 text-xs text-zinc-400">{timeAgo(activity.created_at)}</p>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card className="mt-6">
        <CardBody>
          <div className="flex flex-col items-start gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Phase 1: prepare, don't send</h3>
              <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
                {data.stats.messages_sent === 0
                  ? 'No messages have been sent. SMS sending activates in Phase 2 with a real Android device.'
                  : `Messages sent: ${formatNumber(data.stats.messages_sent)}`}
              </p>
            </div>
            <Link to="/devices" className="text-sm font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400">
              Learn about device pairing →
            </Link>
          </div>
        </CardBody>
      </Card>
    </div>
  )
}
