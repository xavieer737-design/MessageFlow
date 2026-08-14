import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, Eye, Pause, Play, Plus, Send, Trash2, XCircle } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { StatusBadge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { ConfirmDialog } from '../components/ui/Modal'
import { Dropdown, DropdownItem } from '../components/ui/Dropdown'
import { EmptyState } from '../components/ui/EmptyState'
import { PageHeader, SearchInput, useDebouncedValue } from '../components/ui/Misc'
import { Pagination, Table, Td, Th, THead, TRow } from '../components/ui/Table'
import { useToast } from '../components/ui/Toast'
import { getErrorMessage } from '../lib/api'
import { formatDate, formatNumber } from '../lib/format'
import { campaignsApi } from '../services/api'
import type { Campaign } from '../types'

const PAGE_SIZE = 20

export function CampaignsPage() {
  const queryClient = useQueryClient()
  const { success, error } = useToast()
  const navigate = useNavigate()

  const [search, setSearch] = useState('')
  const debouncedSearch = useDebouncedValue(search, 300)
  const [statusFilter, setStatusFilter] = useState('')
  const [page, setPage] = useState(1)
  const [deleteTarget, setDeleteTarget] = useState<Campaign | null>(null)
  const [deleting, setDeleting] = useState(false)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['campaigns', { debouncedSearch, statusFilter, page }],
    queryFn: () =>
      campaignsApi.list({
        search: debouncedSearch,
        status: statusFilter || undefined,
        page,
        page_size: PAGE_SIZE,
      }),
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['campaigns'] })
    queryClient.invalidateQueries({ queryKey: ['dashboard'] })
  }

  const removeCampaign = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await campaignsApi.remove(deleteTarget.id)
      success('Campaign deleted')
      refresh()
      setDeleteTarget(null)
    } catch (err) {
      error(getErrorMessage(err, 'Could not delete campaign'))
    } finally {
      setDeleting(false)
    }
  }

  const runAction = async (campaign: Campaign, action: 'duplicate' | 'pause' | 'resume' | 'cancel') => {
    try {
      const result = await {
        duplicate: () => campaignsApi.duplicate(campaign.id),
        pause: () => campaignsApi.pause(campaign.id),
        resume: () => campaignsApi.resume(campaign.id),
        cancel: () => campaignsApi.cancel(campaign.id),
      }[action]()
      success(`Campaign ${action === 'duplicate' ? 'duplicated' : result.status.toLowerCase()}`)
      refresh()
    } catch (err) {
      error(getErrorMessage(err, 'Action failed'))
    }
  }

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Campaigns"
        description="Prepare campaigns in a wizard — validate recipients, preview messages, and save as DRAFT or READY. Sending arrives in Phase 2."
        actions={
          <Link to="/campaigns/new">
            <Button>
              <Plus className="h-4 w-4" /> New campaign
            </Button>
          </Link>
        }
      />

      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center">
        <SearchInput value={search} onChange={setSearch} placeholder="Search campaigns…" className="w-full sm:w-64" />
        <select
          value={statusFilter}
          onChange={(event) => { setStatusFilter(event.target.value); setPage(1) }}
          className="h-9 rounded-lg border border-zinc-300 bg-white px-3 text-sm focus:border-brand-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-900"
        >
          <option value="">All statuses</option>
          <option value="DRAFT">DRAFT</option>
          <option value="READY">READY</option>
          <option value="PAUSED">PAUSED</option>
          <option value="CANCELLED">CANCELLED</option>
        </select>
      </div>

      <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-card dark:border-zinc-800 dark:bg-zinc-900">
        {isLoading ? (
          <div className="animate-pulse space-y-0">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="flex gap-4 border-b border-zinc-100 px-5 py-4 dark:border-zinc-800">
                <div className="h-3.5 w-1/4 rounded bg-zinc-100 dark:bg-zinc-800" />
                <div className="h-3.5 w-16 rounded bg-zinc-100 dark:bg-zinc-800" />
                <div className="ml-auto h-3.5 w-20 rounded bg-zinc-100 dark:bg-zinc-800" />
              </div>
            ))}
          </div>
        ) : isError ? (
          <EmptyState title="Could not load campaigns" description="Check that the backend is running and try again." />
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            icon={Send}
            title={debouncedSearch || statusFilter ? 'No campaigns match your filters' : 'No campaigns yet'}
            description="Create a campaign to choose recipients, personalize a message, and validate everything before Phase 2 sending."
            action={
              debouncedSearch || statusFilter ? undefined : (
                <Link to="/campaigns/new">
                  <Button><Plus className="h-4 w-4" /> New campaign</Button>
                </Link>
              )
            }
          />
        ) : (
          <>
            <Table>
              <THead>
                <tr className="border-b border-zinc-200 bg-zinc-50/80 dark:border-zinc-800 dark:bg-zinc-800/40">
                  <Th>Campaign</Th>
                  <Th>Recipients</Th>
                  <Th>Message</Th>
                  <Th>Status</Th>
                  <Th>Created</Th>
                  <Th className="w-14" />
                </tr>
              </THead>
              <tbody>
                {data.items.map((campaign) => (
                  <TRow key={campaign.id}>
                    <Td>
                      <Link to={`/campaigns/${campaign.id}`} className="font-medium text-zinc-900 hover:text-brand-600 dark:text-zinc-100 dark:hover:text-brand-400">
                        {campaign.name}
                      </Link>
                      <p className="text-xs text-zinc-400">
                        {formatNumber(campaign.recipient_count)} recipients · {campaign.pending_count} pending
                      </p>
                    </Td>
                    <Td className="text-sm">
                      <div className="flex items-center gap-1.5">
                        <span className="font-medium text-zinc-800 dark:text-zinc-200">{formatNumber(campaign.recipient_count)}</span>
                        <span className="text-xs text-zinc-400">total</span>
                      </div>
                      {campaign.opted_out_count > 0 && (
                        <p className="text-xs text-amber-600 dark:text-amber-400">{campaign.opted_out_count} opted out</p>
                      )}
                    </Td>
                    <Td className="max-w-64">
                      <p className="line-clamp-2 font-mono text-xs text-zinc-500 dark:text-zinc-400">{campaign.message_template}</p>
                    </Td>
                    <Td><StatusBadge status={campaign.status} /></Td>
                    <Td className="text-xs whitespace-nowrap">{formatDate(campaign.created_at)}</Td>
                    <Td>
                      <Dropdown>
                        {(close) => (
                          <>
                            <DropdownItem icon={<Eye className="h-4 w-4" />} onClick={() => { navigate(`/campaigns/${campaign.id}`); close() }}>
                              View
                            </DropdownItem>
                            {campaign.status === 'DRAFT' && (
                              <DropdownItem icon={<Send className="h-4 w-4" />} onClick={() => { navigate(`/campaigns/${campaign.id}/edit`); close() }}>
                                Edit draft
                              </DropdownItem>
                            )}
                            <DropdownItem icon={<Copy className="h-4 w-4" />} onClick={() => { runAction(campaign, 'duplicate'); close() }}>
                              Duplicate
                            </DropdownItem>
                            {['READY', 'RUNNING', 'SCHEDULED'].includes(campaign.status) && (
                              <DropdownItem icon={<Pause className="h-4 w-4" />} onClick={() => { runAction(campaign, 'pause'); close() }}>
                                Pause
                              </DropdownItem>
                            )}
                            {campaign.status === 'PAUSED' && (
                              <DropdownItem icon={<Play className="h-4 w-4" />} onClick={() => { runAction(campaign, 'resume'); close() }}>
                                Resume
                              </DropdownItem>
                            )}
                            {!['COMPLETED', 'CANCELLED'].includes(campaign.status) && (
                              <DropdownItem danger icon={<XCircle className="h-4 w-4" />} onClick={() => { runAction(campaign, 'cancel'); close() }}>
                                Cancel
                              </DropdownItem>
                            )}
                            <DropdownItem danger icon={<Trash2 className="h-4 w-4" />} onClick={() => { setDeleteTarget(campaign); close() }}>
                              Delete
                            </DropdownItem>
                          </>
                        )}
                      </Dropdown>
                    </Td>
                  </TRow>
                ))}
              </tbody>
            </Table>
            <Pagination page={data.page} pages={data.pages} total={data.total} onChange={setPage} />
          </>
        )}
      </div>

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={removeCampaign}
        loading={deleting}
        title="Delete campaign"
        message={<>Delete campaign <strong>{deleteTarget?.name}</strong>? This removes its recipients and message logs.</>}
      />
    </div>
  )
}
