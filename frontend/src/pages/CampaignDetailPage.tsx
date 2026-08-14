import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Copy,
  ListChecks,
  Pause,
  Play,
  Send,
  Smartphone,
  Trash2,
  XCircle,
} from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Badge, StatusBadge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { ConfirmDialog } from '../components/ui/Modal'
import { Modal } from '../components/ui/Modal'
import { EmptyState } from '../components/ui/EmptyState'
import { Alert, Spinner } from '../components/ui/Misc'
import { Table, Td, Th, THead, TRow } from '../components/ui/Table'
import { useToast } from '../components/ui/Toast'
import { getErrorMessage } from '../lib/api'
import { formatDateTime, formatNumber, timeAgo } from '../lib/format'
import { campaignsApi, devicesApi } from '../services/api'
import type { CampaignValidationReport, Device } from '../types'
import { cn } from '../lib/cn'

export function CampaignDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { success, error } = useToast()
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [validating, setValidating] = useState(false)
  const [report, setReport] = useState<CampaignValidationReport | null>(null)
  const [sendModalOpen, setSendModalOpen] = useState(false)
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null)
  const [sending, setSending] = useState(false)

  const { data: campaign, isLoading, isError } = useQuery({
    queryKey: ['campaign', id],
    queryFn: () => campaignsApi.get(Number(id)),
    enabled: !!id,
  })

  const isSending = campaign?.status === 'RUNNING' || campaign?.status === 'PAUSED'

  const { data: progress } = useQuery({
    queryKey: ['campaign-progress', id],
    queryFn: () => campaignsApi.progress(Number(id)),
    enabled: !!id && isSending,
    refetchInterval: isSending ? 4000 : false,
  })

  const { data: devices } = useQuery({
    queryKey: ['devices'],
    queryFn: devicesApi.list,
    enabled: sendModalOpen || campaign?.status === 'READY',
    refetchInterval: 8000,
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['campaign', id] })
    queryClient.invalidateQueries({ queryKey: ['campaigns'] })
    queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    queryClient.invalidateQueries({ queryKey: ['messages'] })
    queryClient.invalidateQueries({ queryKey: ['campaign-progress'] })
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

  const startSend = async () => {
    if (!campaign || !selectedDevice) return
    setSending(true)
    try {
      const result = await campaignsApi.send(campaign.id, selectedDevice.id)
      success(result.message)
      setSendModalOpen(false)
      setSelectedDevice(null)
      refresh()
    } catch (err) {
      error(getErrorMessage(err, 'Could not start the campaign'))
    } finally {
      setSending(false)
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
  const connectedDevices = devices?.filter((d) => d.is_online) ?? []

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
          {campaign.status === 'READY' && (
            <Button onClick={() => setSendModalOpen(true)}>
              <Send className="h-4 w-4" /> Send Campaign
            </Button>
          )}
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
          <Button variant="outline" onClick={() => runAction('duplicate')}>
            <Copy className="h-4 w-4" /> Duplicate
          </Button>
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

      {isSending && (
        <Card className="mb-6 border-brand-200 dark:border-brand-500/30">
          <CardBody>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Send progress</h3>
                {progress?.device_name && (
                  <Badge tone="gray">
                    <Smartphone className="h-3 w-3" /> {progress.device_name}
                    {progress.device_connection_status && ` · ${progress.device_connection_status.toLowerCase()}`}
                  </Badge>
                )}
                {progress?.job_status && <StatusBadge status={progress.job_status} />}
              </div>
              <p className="text-xs text-zinc-400">
                {progress ? `${formatNumber(progress.sent + progress.failed + progress.skipped + progress.opted_out)} / ${formatNumber(progress.total)}` : '…'}
                {campaign.status === 'PAUSED' && <span className="ml-2 text-amber-600">paused — no new sends until resumed</span>}
              </p>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
              <div
                className="h-full rounded-full bg-brand-500 transition-all duration-700"
                style={{ width: `${Math.round((progress?.progress ?? 0) * 100)}%` }}
              />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-7">
              <ProgressStat label="Pending" value={progress?.pending ?? 0} />
              <ProgressStat label="Queued" value={progress?.queued ?? 0} />
              <ProgressStat label="Processing" value={progress?.processing ?? 0} tone="text-blue-600" />
              <ProgressStat label="Sent" value={progress?.sent ?? 0} tone="text-emerald-600" />
              <ProgressStat label="Failed" value={progress?.failed ?? 0} tone={progress?.failed ? 'text-red-600' : ''} />
              <ProgressStat label="Skipped" value={progress?.skipped ?? 0} />
              <ProgressStat label="Opted out" value={progress?.opted_out ?? 0} tone={progress?.opted_out ? 'text-amber-600' : ''} />
            </div>
            {progress && progress.progress === 1 && progress.campaign_status !== 'COMPLETED' && (
              <p className="mt-3 text-xs text-zinc-400">All recipients reached a terminal state.</p>
            )}
          </CardBody>
        </Card>
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
                    : campaign.status === 'READY'
                      ? 'This campaign is validated and ready. Choose a connected device to start sending.'
                      : campaign.status === 'RUNNING'
                        ? 'Sending is in progress. Only the Android device\'s reported results change message states.'
                        : 'This campaign is prepared. No SMS is sent without a connected device.'}
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
                <SummaryRow label="Queued" value={formatNumber(campaign.queued_count)} />
                <SummaryRow label="Processing" value={formatNumber(campaign.processing_count)} />
                <SummaryRow label="Sent" value={formatNumber(campaign.sent_count)} />
                <SummaryRow label="Failed" value={formatNumber(campaign.failed_count)} />
                <SummaryRow label="Skipped" value={formatNumber(campaign.skipped_count)} />
                <SummaryRow label="Opted out" value={formatNumber(campaign.opted_out_count)} />
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

          {progress?.device_name && (
            <Card>
              <CardHeader title="Sending device" />
              <CardBody>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">{progress.device_name}</p>
                    <p className="text-xs text-zinc-400">{timeAgo(campaign.updated_at)} since last update</p>
                  </div>
                  {progress.device_connection_status && <StatusBadge status={progress.device_connection_status} />}
                </div>
              </CardBody>
            </Card>
          )}
        </div>
      </div>

      {/* Device selection for sending */}
      <Modal
        open={sendModalOpen}
        onClose={() => setSendModalOpen(false)}
        title="Send Campaign"
        description="Choose the Android device that will send the messages through its SIM."
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={() => setSendModalOpen(false)}>Cancel</Button>
            <Button onClick={startSend} disabled={!selectedDevice} loading={sending}>
              <Send className="h-4 w-4" /> Start sending
            </Button>
          </>
        }
      >
        {devices && devices.length === 0 ? (
          <EmptyState
            icon={Smartphone}
            title="No Android device connected"
            description="Pair a device on the Devices page before sending this campaign."
            action={
              <Link to="/devices"><Button variant="outline">Go to Devices</Button></Link>
            }
          />
        ) : (
          <div className="space-y-2">
            {connectedDevices.length === 0 && (
              <Alert tone="warning">No device is online right now. Connect the Android app before sending.</Alert>
            )}
            {devices?.map((device) => (
              <label
                key={device.id}
                className={cn(
                  'flex cursor-pointer items-center justify-between gap-3 rounded-lg border px-4 py-3 transition-colors',
                  selectedDevice?.id === device.id
                    ? 'border-brand-500 bg-brand-50/50 dark:border-brand-500 dark:bg-brand-500/10'
                    : 'border-zinc-200 hover:border-zinc-300 dark:border-zinc-700 dark:hover:border-zinc-600',
                  !device.is_online && 'opacity-60',
                )}
              >
                <div className="flex items-center gap-3">
                  <input
                    type="radio"
                    name="device"
                    checked={selectedDevice?.id === device.id}
                    disabled={!device.is_online}
                    onChange={() => setSelectedDevice(device)}
                    className="h-4 w-4 accent-brand-600"
                  />
                  <div>
                    <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">{device.device_name}</p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">
                      {device.phone_model ?? 'Model unknown'}
                      {device.battery_level !== null && ` · Battery ${device.battery_level}%`}
                      {device.sim_state && ` · SIM ${device.sim_state}`}
                    </p>
                  </div>
                </div>
                <StatusBadge status={device.is_online ? 'CONNECTED' : device.connection_status} />
              </label>
            ))}
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={removeCampaign}
        loading={deleting}
        title="Delete campaign"
        message={<>Delete campaign <strong>{campaign.name}</strong>? This removes its recipients, send queue and message logs.</>}
      />
    </div>
  )
}

function ProgressStat({ label, value, tone = '' }: { label: string; value: number; tone?: string }) {
  return (
    <div className="rounded-lg border border-zinc-100 px-2 py-1.5 dark:border-zinc-800">
      <p className={`text-sm font-bold ${tone || 'text-zinc-800 dark:text-zinc-100'}`}>{value}</p>
      <p className="text-[10px] font-semibold tracking-wide text-zinc-400 uppercase">{label}</p>
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
