import { useQuery } from '@tanstack/react-query'
import { ScrollText } from 'lucide-react'
import { useState } from 'react'
import { StatusBadge } from '../components/ui/Badge'
import { EmptyState } from '../components/ui/EmptyState'
import { PageHeader, Tabs } from '../components/ui/Misc'
import { Pagination, Table, Td, Th, THead, TRow } from '../components/ui/Table'
import { formatDateTime } from '../lib/format'
import { messagesApi } from '../services/api'

const PAGE_SIZE = 25

const FILTERS = [
  { id: '', label: 'All' },
  { id: 'PENDING', label: 'Pending' },
  { id: 'SENT', label: 'Sent' },
  { id: 'FAILED', label: 'Failed' },
  { id: 'SKIPPED', label: 'Skipped' },
  { id: 'OPTED_OUT', label: 'Opted Out' },
]

export function MessageLogsPage() {
  const [filter, setFilter] = useState('')
  const [page, setPage] = useState(1)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['messages', { filter, page }],
    queryFn: () => messagesApi.list({ status: filter || undefined, page, page_size: PAGE_SIZE }),
  })

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Message Logs"
        description="Records created by real application operations — validation skips and opt-outs. Delivery logs appear in Phase 2."
      />

      <div className="mb-4">
        <Tabs tabs={FILTERS} active={filter} onChange={(id) => { setFilter(id); setPage(1) }} />
      </div>

      <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-card dark:border-zinc-800 dark:bg-zinc-900">
        {isLoading ? (
          <div className="animate-pulse">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="flex gap-4 border-b border-zinc-100 px-5 py-4 dark:border-zinc-800">
                <div className="h-3.5 w-24 rounded bg-zinc-100 dark:bg-zinc-800" />
                <div className="h-3.5 w-32 rounded bg-zinc-100 dark:bg-zinc-800" />
                <div className="h-3.5 w-40 rounded bg-zinc-100 dark:bg-zinc-800" />
                <div className="ml-auto h-3.5 w-16 rounded bg-zinc-100 dark:bg-zinc-800" />
              </div>
            ))}
          </div>
        ) : isError ? (
          <EmptyState title="Could not load message logs" description="Check that the backend is running and try again." />
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            icon={ScrollText}
            title={filter ? `No ${filter.toLowerCase()} messages` : 'No message logs yet'}
            description={
              filter
                ? 'No records match this filter.'
                : 'When you validate campaigns, skipped and opted-out recipients are logged here. Sent/failed delivery records will appear once real devices send in Phase 2.'
            }
          />
        ) : (
          <>
            <Table>
              <THead>
                <tr className="border-b border-zinc-200 bg-zinc-50/80 dark:border-zinc-800 dark:bg-zinc-800/40">
                  <Th>Timestamp</Th>
                  <Th>Campaign</Th>
                  <Th>Recipient</Th>
                  <Th>Phone</Th>
                  <Th>Status</Th>
                  <Th>Error</Th>
                  <Th>Device</Th>
                </tr>
              </THead>
              <tbody>
                {data.items.map((log) => (
                  <TRow key={log.id}>
                    <Td className="text-xs whitespace-nowrap">{formatDateTime(log.created_at)}</Td>
                    <Td className="max-w-40 truncate">{log.campaign_name ?? '—'}</Td>
                    <Td className="max-w-32 truncate">{log.contact_name ?? '—'}</Td>
                    <Td className="font-mono text-xs">{log.phone ?? '—'}</Td>
                    <Td><StatusBadge status={log.status} /></Td>
                    <Td className="max-w-48 truncate text-xs text-amber-600 dark:text-amber-400">{log.error ?? '—'}</Td>
                    <Td className="text-xs">{log.device_name ?? '—'}</Td>
                  </TRow>
                ))}
              </tbody>
            </Table>
            <Pagination page={data.page} pages={data.pages} total={data.total} onChange={setPage} />
          </>
        )}
      </div>
    </div>
  )
}
