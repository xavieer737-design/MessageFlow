import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Copy, ListChecks, Pause, Play, Send, Trash2, XCircle } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Badge, StatusBadge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { ConfirmDialog } from '../components/ui/Modal'
import { EmptyState } from '../components/ui/EmptyState'
import { Alert, Spinner } from '../components/ui/Misc'
import { Table, Td, Th, THead, TRow } from '../components/ui/Table'
import { useToast } from '../components/ui/Toast'
import { getErrorMessage } from '../lib/api'
import { formatDateTime, formatNumber } from '../lib/format'
import { campaignsApi } from '../services/api'
import type { CampaignValidationReport } from '../types'

export function CampaignDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { success, error } = useToast()
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [validating, setValidating] = useState(false)
  const [report, setReport] = useState<CampaignValidationReport | null>(null)

  const { data: campaign, isLoading, isError } = useQuery({
    queryKey: ['campaign', id],
    queryFn: () => campaignsApi.get(Number(id)),
    enabled: !!id,
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['campaign', id] })
    queryClient.invalidateQueries({ queryKey: ['campaigns'] })
    queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    queryClient.invalidateQueries({ queryKey: ['messages'] })
  }

  const runAction = async (action: 'duplicate' | 'pause' | 'resume' | 'cancel' | 'ready') => {
    if (!campaign) return
    try {
      const result = await {
        duplicate: () => campaignsApi.duplicate(campaign.id),
        pause: () => campaignsApi.pause(campaign.id),
        resume: () => campaignsApi.resume(campaign.id),
        cancel: () => campaignsApi.cancel(campaign.id),
        ready: () => campaignsApi.markReady(campaign.id),
      }[action]()
      success(action === 'duplicate' ? 'Campaign duplicated' : `Campaign ${result.status.toLowerCase()}`)
      refresh()
    } catch (err) {
      error(getErrorMessage(err, 'Action failed'))
    }
  }

  const validateNow = async () => {
    if (!campaign) return
    setValidating(true)
    try {
      const result = await campaignsApi.validate(campaign.id)
      setReport(result)
      if (result.valid) success('Validation passed')
      else error('Validation found issues')
      refresh()
    } catch (err) {
      error(getErrorMessage(err, 'Validation failed'))
    } finally {
      setValidating(false)
    }
  }

  const removeCampaign = async () => {
    if (!campaign) return
    setDeleting(true)
    try {
      await campaignsApi.remove(campaign.id)
      success('Campaign deleted')
      navigate('/campaigns')
    } catch (err) {
      error(getErrorMessage(err, 'Could not delete campaign'))
    } finally {
      setDeleting(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-24">
        <Spinner className="h-7 w-7" />
      </div>
    )
  }

  if (isError || !campaign) {
    return <EmptyState title="Campaign not found" description="It may have been deleted." action={<Link to="/campaigns"><Button variant="outline"><ArrowLeft className="h-4 w-4" /> Back to campaigns</Button></Link>} />
  }

  const canEdit = campaign.status === 'DRAFT'

  return (
    <div className="mx-auto max-w-5xl animate-fade-in">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Link to="/campaigns" className="inline-flex items-center gap-1 text-xs font-medium text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200">
            <ArrowLeft className="h-3.5 w-3.5" /> Campaigns
          </Link>
          <div className="mt-1 flex flex-wrap items-center gap-2.5">
            <h1 className="text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50">{campaign.name}</h1>
            <StatusBadge status={campaign.status} />
          </div>
          <p className="mt-0.5 text-sm text-zinc-500">Created {formatDateTime(campaign.created_at)}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {canEdit && (
            <Button variant="outline" onClick={() => navigate(`/campaigns/${campaign.id}/edit`)}>
              <Send className="h-4 w-4" /> Edit draft
            </Button>
          )}
          {campaign.status === 'DRAFT' && (
            <Button onClick={validateNow} loading={validating}>
              <ListChecks className="h-4 w-4" /> Validate
            </Button>
          )}
          <Button variant="outline" onClick={() => runAction('duplicate')}>
            <Copy className="h-4 w-4" /> Duplicate
          </Button>
          {['READY', 'RUNNING', 'SCHEDULED'].includes(campaign.status) && (
            <Button variant="outline" onClick={() => runAction('pause')}>
              <Pause className="h-4 w-4" /> Pause
            </Button>
          )}
          {campaign.status === 'PAUSED' && (
            <Button variant="outline" onClick={() => runAction('resume')}>
              <Play className="h-4 w-4" /> Resume
            </Button>
          )}
          {!['COMPLETED', 'CANCELLED'].includes(campaign.status) && (
            <Button variant="outline" onClick={() => runAction('cancel')}>
              <XCircle className="h-4 w-4" /> Cancel
            </Button>
          )}
          <Button variant="danger" onClick={() => setDeleteOpen(true)}>
            <Trash2 className="h-4 w-4" /> Delete
          </Button>
        </div>
      </div>

      {report && report.errors.length > 0 && (
        <div className="mb-4 space-y-2">
          {report.errors.map((issue, index) => (
            <Alert key={index} tone="error">{issue.message}</Alert>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader title="Message" description="Template with variables — personalized per recipient" />
            <CardBody>
              <p className="rounded-lg bg-zinc-50 px-4 py-3 font-mono text-xs leading-relaxed whitespace-pre-wrap dark:bg-zinc-800/50">
                {campaign.message_template}
              </p>
              <div className="mt-3">
                <Alert tone="info">
                  {campaign.status === 'DRAFT'
                    ? 'This campaign is a draft. Validate it to generate personalized messages and mark it READY.'
                    : 'This campaign is prepared and validated. Sending starts in Phase 2 when an Android device is connected.'}
                </Alert>
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Recipients"
              description={`${formatNumber(campaign.recipient_count)} total — personalized messages and statuses`}
            />
            {campaign.recipients.length === 0 ? (
              <EmptyState
                icon={Send}
                title="No recipients prepared yet"
                description="Run validation to generate personalized messages for every recipient."
              />
            ) : (
              <div className="max-h-[420px] overflow-y-auto">
                <Table>
                  <THead>
                    <tr className="border-b border-zinc-200 bg-zinc-50/80 dark:border-zinc-800 dark:bg-zinc-800/40">
                      <Th>Status</Th>
                      <Th>Contact</Th>
                      <Th>Personalized message</Th>
                      <Th>Error</Th>
                    </tr>
                  </THead>
                  <tbody>
                    {campaign.recipients.slice(0, 100).map((recipient) => (
                      <TRow key={recipient.id}>
                        <Td><StatusBadge status={recipient.status} /></Td>
                        <Td>
                          <p className="text-xs text-zinc-500">contact #{recipient.contact_id ?? '—'}</p>
                        </Td>
                        <Td className="max-w-72">
                          <p className="line-clamp-2 text-xs whitespace-pre-wrap text-zinc-600 dark:text-zinc-300">
                            {recipient.personalized_message ?? '—'}
                          </p>
                        </Td>
                        <Td className="max-w-40 text-xs text-amber-600 dark:text-amber-400">{recipient.error ?? '—'}</Td>
                      </TRow>
                    ))}
                  </tbody>
                </Table>
                {campaign.recipients.length > 100 && (
                  <p className="px-4 py-2 text-xs text-zinc-400">
                    Showing the first 100 of {formatNumber(campaign.recipients.length)} recipients.
                  </p>
                )}
              </div>
            )}
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader title="Summary" />
            <CardBody>
              <dl className="space-y-3">
                <SummaryRow label="Total recipients" value={formatNumber(campaign.recipient_count)} />
                <SummaryRow label="Pending" value={formatNumber(campaign.pending_count)} />
                <SummaryRow label="Opted out (skipped)" value={formatNumber(campaign.opted_out_count)} />
                <SummaryRow label="Skipped" value={formatNumber(campaign.skipped_count)} />
                <SummaryRow label="Sent" value={formatNumber(campaign.sent_count)} note="Phase 2" />
                <SummaryRow label="Failed" value={formatNumber(campaign.failed_count)} note="Phase 2" />
              </dl>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Targeting" />
            <CardBody>
              <dl className="space-y-3">
                <SummaryRow
                  label="Recipients"
                  value={
                    campaign.recipient_scope === 'all'
                      ? 'All contacts'
                      : campaign.recipient_scope === 'group'
                        ? `Group #${campaign.recipient_group_id ?? '—'}`
                        : `${campaign.recipient_contact_ids.length} selected contact(s)`
                  }
                />
                <SummaryRow label="Scheduled" value={campaign.scheduled_at ? formatDateTime(campaign.scheduled_at) : 'Not scheduled'} />
                <SummaryRow label="Created" value={formatDateTime(campaign.created_at)} />
              </dl>
            </CardBody>
          </Card>

          <Card className="border-amber-200 dark:border-amber-500/30">
            <CardBody>
              <div className="flex items-start gap-2.5">
                <Badge tone="amber">Phase 1</Badge>
                <p className="text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">
                  No SMS has been sent from this campaign. Sending requires a connected Android device, which arrives in Phase 2.
                </p>
              </div>
            </CardBody>
          </Card>
        </div>
      </div>

      <ConfirmDialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={removeCampaign}
        loading={deleting}
        title="Delete campaign"
        message={<>Delete campaign <strong>{campaign.name}</strong>? This removes its recipients and message logs.</>}
      />
    </div>
  )
}

function SummaryRow({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-xs font-medium text-zinc-500 dark:text-zinc-400">{label}</dt>
      <dd className="text-sm font-semibold text-zinc-800 dark:text-zinc-100">
        {value}
        {note && <span className="ml-1 text-[10px] font-normal text-zinc-400">{note}</span>}
      </dd>
    </div>
  )
}
