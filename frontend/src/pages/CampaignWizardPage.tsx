import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  FileText,
  ListChecks,
  MessageSquareText,
  Save,
  Users,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Badge, StatusBadge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardBody } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { Field, Input, Select, Textarea } from '../components/ui/Form'
import { Alert, PageHeader, Spinner } from '../components/ui/Misc'
import { useToast } from '../components/ui/Toast'
import { getErrorMessage } from '../lib/api'
import { analyzeSms } from '../lib/smsCounter'
import { extractVariables, insertVariable, personalize, VARIABLE_LABELS } from '../lib/templateVars'
import { campaignsApi, contactsApi, groupsApi, templatesApi } from '../services/api'
import type { CampaignValidationReport, RecipientTarget } from '../types'
import { cn } from '../lib/cn'

const STEPS = ['Details', 'Recipients', 'Message', 'Preview', 'Validation', 'Save']

export function CampaignWizardPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { success, error } = useToast()

  const [step, setStep] = useState(0)
  const [name, setName] = useState('')
  const [message, setMessage] = useState('')
  const [scope, setScope] = useState<'all' | 'group' | 'contacts'>('all')
  const [groupId, setGroupId] = useState<number | ''>('')
  const [contactIds, setContactIds] = useState<number[]>([])
  const [report, setReport] = useState<CampaignValidationReport | null>(null)
  const [saving, setSaving] = useState(false)
  const [loadingReport, setLoadingReport] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [campaignId, setCampaignId] = useState<number | null>(id ? Number(id) : null)

  const { data: groups } = useQuery({ queryKey: ['groups'], queryFn: groupsApi.list })
  const { data: templates } = useQuery({ queryKey: ['templates'], queryFn: templatesApi.list })
  const { data: contactsPage } = useQuery({
    queryKey: ['contacts', { all: true }],
    queryFn: () => contactsApi.list({ page_size: 200, sort_by: 'created_at', sort_dir: 'desc' }),
  })
  const { data: existing } = useQuery({
    queryKey: ['campaign', id],
    queryFn: () => campaignsApi.get(Number(id)),
    enabled: !!id,
  })

  // Load an existing draft when editing.
  useEffect(() => {
    if (!existing || loaded) return
    setName(existing.name)
    setMessage(existing.message_template)
    setScope(existing.recipient_scope === 'group' || existing.recipient_scope === 'contacts' ? existing.recipient_scope : 'all')
    setGroupId(existing.recipient_group_id ?? '')
    setContactIds(existing.recipient_contact_ids ?? [])
    setLoaded(true)
  }, [existing, loaded])

  const target: RecipientTarget = useMemo(() => {
    if (scope === 'group') return { scope, group_id: groupId === '' ? null : Number(groupId) }
    if (scope === 'contacts') return { scope, contact_ids: contactIds }
    return { scope: 'all' }
  }, [scope, groupId, contactIds])

  const variables = extractVariables(message)
  const sms = analyzeSms(message)

  const allContacts = contactsPage?.items ?? []
  const selectedCount =
    scope === 'all'
      ? allContacts.length
      : scope === 'group'
        ? groups?.find((g) => g.id === Number(groupId))?.contact_count ?? 0
        : contactIds.length

  const canContinue =
    step === 0 ? name.trim().length >= 1
    : step === 1 ? (scope === 'group' ? groupId !== '' : scope === 'contacts' ? contactIds.length > 0 : true)
    : step === 2 ? message.trim().length > 0 && variables.unsupported.length === 0
    : step === 3 ? true
    : step === 4 ? !!report
    : true

  const ensureDraft = async (): Promise<number | null> => {
    if (campaignId) {
      try {
        await campaignsApi.update(campaignId, {
          name: name.trim(),
          message_template: message,
          recipients: target,
        })
        return campaignId
      } catch (err) {
        error(getErrorMessage(err, 'Could not update the draft'))
        return null
      }
    }
    try {
      const created = await campaignsApi.create({
        name: name.trim(),
        message_template: message,
        recipients: target,
        status: 'DRAFT',
      })
      setCampaignId(created.id)
      queryClient.invalidateQueries({ queryKey: ['campaigns'] })
      return created.id
    } catch (err) {
      error(getErrorMessage(err, 'Could not create the draft'))
      return null
    }
  }

  const runValidation = async () => {
    const targetId = await ensureDraft()
    if (!targetId) return
    setLoadingReport(true)
    try {
      const result = await campaignsApi.validate(targetId)
      setReport(result)
      if (!result.valid) {
        error('Validation found issues — review the errors below')
      } else {
        success('Validation passed — recipients prepared')
      }
      queryClient.invalidateQueries({ queryKey: ['campaigns'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    } catch (err) {
      error(getErrorMessage(err, 'Validation failed'))
    } finally {
      setLoadingReport(false)
    }
  }

  const saveCampaign = async (saveStatus: 'DRAFT' | 'READY') => {
    setSaving(true)
    try {
      const targetId = await ensureDraft()
      if (!targetId) return
      if (saveStatus === 'READY') {
        await campaignsApi.markReady(targetId)
      }
      success(saveStatus === 'READY' ? 'Campaign is ready (nothing sent — Phase 2 sends)' : 'Campaign saved as draft')
      queryClient.invalidateQueries({ queryKey: ['campaigns'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      navigate('/campaigns')
    } catch (err) {
      error(getErrorMessage(err, 'Could not save campaign'))
    } finally {
      setSaving(false)
    }
  }

  const previewContacts = allContacts.slice(0, 5)

  const previewFor = (contact: (typeof allContacts)[number]) => {
    const { text, missing } = personalize(message, {
      first_name: contact.first_name ?? '',
      last_name: contact.last_name ?? '',
      phone: contact.phone,
      email: contact.email ?? '',
      company: contact.company ?? '',
      notes: contact.notes ?? '',
    })
    return { text, missing }
  }

  return (
    <div className="mx-auto max-w-4xl animate-fade-in">
      <PageHeader
        title={id ? 'Edit campaign' : 'New campaign'}
        description="Six steps: details, recipients, message, preview, validation, and save. Nothing is sent in Phase 1."
        actions={
          <Button variant="ghost" onClick={() => navigate('/campaigns')}>
            <ArrowLeft className="h-4 w-4" /> Back to campaigns
          </Button>
        }
      />

      {/* Stepper */}
      <div className="mb-6 flex items-center gap-1 overflow-x-auto pb-1">
        {STEPS.map((label, index) => (
          <div key={label} className="flex min-w-0 flex-1 items-center gap-1">
            <button
              onClick={() => index <= step && setStep(index)}
              className={cn(
                'flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium whitespace-nowrap transition-colors',
                index === step
                  ? 'bg-brand-600 text-white'
                  : index < step
                    ? 'text-emerald-600 hover:bg-emerald-50 dark:text-emerald-400 dark:hover:bg-emerald-500/10'
                    : 'text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300',
              )}
            >
              {index < step ? <CheckCircle2 className="h-3.5 w-3.5" /> : <span>{index + 1}</span>}
              <span className="hidden sm:inline">{label}</span>
            </button>
            {index < STEPS.length - 1 && <div className="mx-1 h-px flex-1 bg-zinc-200 dark:bg-zinc-700" />}
          </div>
        ))}
      </div>

      {/* Step 1 — Details */}
      {step === 0 && (
        <Card>
          <CardBody className="space-y-5">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
                <FileText className="h-4.5 w-4.5" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Campaign details</h2>
                <p className="text-xs text-zinc-500">Give your campaign a clear name.</p>
              </div>
            </div>
            <Field label="Campaign name" required hint="e.g. “Diwali offer — customers”">
              <Input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="My campaign"
                maxLength={160}
              />
            </Field>
          </CardBody>
        </Card>
      )}

      {/* Step 2 — Recipients */}
      {step === 1 && (
        <Card>
          <CardBody className="space-y-5">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
                <Users className="h-4.5 w-4.5" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Recipients</h2>
                <p className="text-xs text-zinc-500">Choose who this campaign targets.</p>
              </div>
            </div>

            <div className="space-y-2">
              {([
                { value: 'all', label: 'All contacts', hint: `${allContacts.length} contact${allContacts.length === 1 ? '' : 's'} in your address book` },
                { value: 'group', label: 'Contact group', hint: 'Target one of your groups' },
                { value: 'contacts', label: 'Selected contacts', hint: 'Pick specific contacts' },
              ] as const).map((option) => (
                <label
                  key={option.value}
                  className={cn(
                    'flex cursor-pointer items-center justify-between gap-3 rounded-lg border px-4 py-3 transition-colors',
                    scope === option.value
                      ? 'border-brand-500 bg-brand-50/50 dark:border-brand-500 dark:bg-brand-500/10'
                      : 'border-zinc-200 hover:border-zinc-300 dark:border-zinc-700 dark:hover:border-zinc-600',
                  )}
                >
                  <div className="flex items-center gap-3">
                    <input
                      type="radio"
                      name="scope"
                      checked={scope === option.value}
                      onChange={() => setScope(option.value)}
                      className="h-4 w-4 accent-brand-600"
                    />
                    <div>
                      <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">{option.label}</p>
                      <p className="text-xs text-zinc-500 dark:text-zinc-400">{option.hint}</p>
                    </div>
                  </div>
                </label>
              ))}
            </div>

            {scope === 'group' && (
              <Field label="Group">
                <Select value={groupId} onChange={(event) => setGroupId(event.target.value === '' ? '' : Number(event.target.value))}>
                  <option value="">Select a group…</option>
                  {groups?.map((group) => (
                    <option key={group.id} value={group.id}>
                      {group.name} ({group.contact_count})
                    </option>
                  ))}
                </Select>
              </Field>
            )}

            {scope === 'contacts' && (
              <div>
                <p className="mb-1.5 text-sm font-medium text-zinc-700 dark:text-zinc-300">Select contacts</p>
                <div className="max-h-64 overflow-y-auto rounded-lg border border-zinc-200 dark:border-zinc-700">
                  {allContacts.length === 0 && (
                    <p className="px-4 py-3 text-sm text-zinc-500">No contacts yet — add or import contacts first.</p>
                  )}
                  {allContacts.map((contact) => (
                    <label
                      key={contact.id}
                      className="flex cursor-pointer items-center gap-3 border-b border-zinc-100 px-4 py-2 last:border-0 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-800/40"
                    >
                      <input
                        type="checkbox"
                        checked={contactIds.includes(contact.id)}
                        onChange={() =>
                          setContactIds((current) =>
                            current.includes(contact.id)
                              ? current.filter((c) => c !== contact.id)
                              : [...current, contact.id],
                          )
                        }
                        className="h-4 w-4 accent-brand-600"
                      />
                      <span className="flex-1 text-sm text-zinc-700 dark:text-zinc-200">
                        {[contact.first_name, contact.last_name].filter(Boolean).join(' ') || 'Unknown'}
                      </span>
                      <span className="font-mono text-xs text-zinc-400">{contact.phone}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            <Alert tone="info">
              <strong>{selectedCount}</strong> recipient{selectedCount === 1 ? '' : 's'} selected. Opted-out numbers are
              excluded automatically during validation.
            </Alert>
          </CardBody>
        </Card>
      )}

      {/* Step 3 — Message */}
      {step === 2 && (
        <Card>
          <CardBody className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
                <MessageSquareText className="h-4.5 w-4.5" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Message</h2>
                <p className="text-xs text-zinc-500">Write your message with {'{{variables}}'}, or start from a template.</p>
              </div>
            </div>

            {templates && templates.length > 0 && (
              <Field label="Start from a template">
                <Select
                  value=""
                  onChange={(event) => {
                    const template = templates.find((t) => t.id === Number(event.target.value))
                    if (template) setMessage(template.message)
                  }}
                >
                  <option value="">Select a template…</option>
                  {templates.map((template) => (
                    <option key={template.id} value={template.id}>{template.name}</option>
                  ))}
                </Select>
              </Field>
            )}

            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Message text</span>
                <span className="text-xs text-zinc-400">Click a variable to insert it</span>
              </div>
              <Textarea
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="Hi {{first_name}}, your order from {{company}} is ready."
                className="min-h-[160px] font-mono text-xs"
              />
            </div>

            <div className="flex flex-wrap gap-1.5">
              {Object.entries(VARIABLE_LABELS).map(([variable, label]) => (
                <button
                  key={variable}
                  type="button"
                  onClick={() => setMessage(insertVariable(message, variable, message.length))}
                  className="rounded-md border border-zinc-200 bg-zinc-50 px-2 py-1 font-mono text-[11px] text-zinc-600 transition-colors hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
                >
                  {`{{${variable}}}`}
                  <span className="ml-1 font-sans text-zinc-400">{label}</span>
                </button>
              ))}
            </div>

            <div className="flex flex-wrap items-center gap-3 rounded-lg border border-zinc-200 bg-zinc-50/60 px-3.5 py-2.5 text-xs text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800/30">
              <span>Characters: <strong className="text-zinc-800 dark:text-zinc-100">{sms.characters}</strong></span>
              <span>SMS segments: <strong className="text-zinc-800 dark:text-zinc-100">{sms.segments}</strong></span>
              <Badge tone={sms.encoding === 'GSM-7' ? 'gray' : 'violet'}>{sms.encoding}</Badge>
              {sms.truncated && <span className="text-amber-600 dark:text-amber-400">⚠ Message splits into {sms.segments} segments</span>}
              {sms.exceedLimit && <span className="font-medium text-red-600 dark:text-red-400">Exceeds 10-segment SMS limit — shorten it.</span>}
            </div>

            {variables.unsupported.length > 0 && (
              <Alert tone="error">
                Unsupported variables: {variables.unsupported.map((v) => `{{${v}}}`).join(', ')}. Supported variables:
                first_name, last_name, phone, email, company, notes.
              </Alert>
            )}
          </CardBody>
        </Card>
      )}

      {/* Step 4 — Preview */}
      {step === 3 && (
        <Card>
          <CardBody className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
                <MessageSquareText className="h-4.5 w-4.5" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Personalized preview</h2>
                <p className="text-xs text-zinc-500">Real personalized messages generated from your actual contacts.</p>
              </div>
            </div>

            {allContacts.length === 0 ? (
              <EmptyState
                icon={Users}
                title="No contacts to preview"
                description="Add or import contacts, then come back to preview personalized messages."
              />
            ) : (
              <div className="space-y-3">
                {previewContacts.map((contact) => {
                  const preview = previewFor(contact)
                  return (
                    <div key={contact.id} className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-700">
                      <div className="mb-2 flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                            {[contact.first_name, contact.last_name].filter(Boolean).join(' ') || 'Unknown'}
                          </p>
                          <p className="font-mono text-xs text-zinc-400">{contact.phone}</p>
                        </div>
                        <Badge tone={contact.company ? 'gray' : 'amber'}>
                          {contact.company ? contact.company : 'no company'}
                        </Badge>
                      </div>
                      <div className="rounded-md bg-zinc-50 px-3.5 py-2.5 dark:bg-zinc-800/50">
                        <p className="text-sm whitespace-pre-wrap text-zinc-800 dark:text-zinc-100">
                          {preview.text || <span className="text-zinc-400">(empty after personalization)</span>}
                        </p>
                      </div>
                      {preview.missing.length > 0 && (
                        <p className="mt-1.5 text-xs text-amber-600 dark:text-amber-400">
                          Missing fields: {preview.missing.join(', ')}
                        </p>
                      )}
                    </div>
                  )
                })}
                {allContacts.length > previewContacts.length && (
                  <p className="text-xs text-zinc-400">
                    Showing {previewContacts.length} of {allContacts.length} recipients — all are personalized during validation.
                  </p>
                )}
              </div>
            )}
          </CardBody>
        </Card>
      )}

      {/* Step 5 — Validation */}
      {step === 4 && (
        <Card>
          <CardBody className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
                <ListChecks className="h-4.5 w-4.5" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Validation</h2>
                <p className="text-xs text-zinc-500">Checks recipients, phones, duplicates, opt-outs, and SMS length.</p>
              </div>
            </div>

            <Alert tone="info">
              Validating {campaignId ? 'updates your draft' : 'creates a draft'}, generates personalized
              messages, and flags any issues — duplicates, invalid phones, opt-outs, unsupported variables and SMS length.
            </Alert>

            {!report && (
              <Button onClick={runValidation} loading={loadingReport}>
                <ListChecks className="h-4 w-4" /> Run validation
              </Button>
            )}

            {loadingReport && (
              <div className="flex items-center gap-2 text-sm text-zinc-500">
                <Spinner className="h-4 w-4" /> Validating {selectedCount} recipient{selectedCount === 1 ? '' : 's'}…
              </div>
            )}

            {report && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <SummaryStat label="Recipients" value={report.total_recipients} />
                  <SummaryStat label="Valid (pending)" value={report.pending} tone="text-emerald-600" />
                  <SummaryStat label="Opted out" value={report.skipped_opted_out} tone={report.skipped_opted_out ? 'text-amber-600' : ''} />
                  <SummaryStat label="Skipped" value={report.skipped_invalid_phone + report.skipped_duplicate + report.skipped_empty_message} tone={report.skipped_invalid_phone ? 'text-red-600' : ''} />
                </div>

                {report.errors.length === 0 && report.warnings.length === 0 && (
                  <Alert tone="success">All checks passed — this campaign is ready to be saved as READY.</Alert>
                )}

                {report.errors.map((issue, index) => (
                  <Alert key={`e-${index}`} tone="error">
                    <span className="font-medium capitalize">{issue.category.replace('_', ' ')}: </span>
                    {issue.message}
                  </Alert>
                ))}
                {report.warnings.map((issue, index) => (
                  <Alert key={`w-${index}`} tone="warning">
                    <span className="font-medium capitalize">{issue.category.replace('_', ' ')}: </span>
                    {issue.message}
                  </Alert>
                ))}

                {report.previews.length > 0 && (
                  <div>
                    <p className="mb-1.5 text-xs font-semibold tracking-wide text-zinc-400 uppercase">
                      Sample personalized messages
                    </p>
                    <div className="max-h-72 space-y-2 overflow-y-auto">
                      {report.previews.map((preview) => (
                        <div key={preview.contact_id} className="rounded-lg border border-zinc-200 px-3.5 py-2.5 dark:border-zinc-700">
                          <div className="mb-1 flex items-center justify-between gap-2">
                            <p className="text-xs font-medium text-zinc-700 dark:text-zinc-200">{preview.name}</p>
                            <StatusBadge status={preview.status} />
                          </div>
                          <p className="text-xs whitespace-pre-wrap text-zinc-500 dark:text-zinc-400">
                            {preview.preview ?? preview.error}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </CardBody>
        </Card>
      )}

      {/* Step 6 — Save */}
      {step === 5 && (
        <Card>
          <CardBody className="space-y-5">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400">
                <Save className="h-4.5 w-4.5" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Save campaign</h2>
                <p className="text-xs text-zinc-500">Phase 1 never sends anything — choose how to prepare it.</p>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <button
                onClick={() => saveCampaign('DRAFT')}
                disabled={saving}
                className="rounded-xl border border-zinc-200 p-5 text-left transition-colors hover:border-brand-300 hover:bg-brand-50/30 disabled:opacity-60 dark:border-zinc-700 dark:hover:bg-brand-500/5"
              >
                <Badge tone="gray">DRAFT</Badge>
                <p className="mt-2 text-sm font-semibold text-zinc-900 dark:text-zinc-100">Save as draft</p>
                <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                  Keep working on it. You can edit, validate and finalize it later.
                </p>
              </button>
              <button
                onClick={() => saveCampaign('READY')}
                disabled={saving || !report?.valid}
                className="rounded-xl border border-zinc-200 p-5 text-left transition-colors hover:border-emerald-300 hover:bg-emerald-50/30 disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-700 dark:hover:bg-emerald-500/5"
              >
                <Badge tone="blue">READY</Badge>
                <p className="mt-2 text-sm font-semibold text-zinc-900 dark:text-zinc-100">Save as ready</p>
                <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                  Validates first; only a passing validation produces a READY campaign.
                </p>
                {!report?.valid && (
                  <p className="mt-2 flex items-center gap-1 text-xs font-medium text-amber-600 dark:text-amber-400">
                    <AlertTriangle className="h-3.5 w-3.5" /> Validate the campaign first
                  </p>
                )}
              </button>
            </div>

            <Alert tone="info">
              <strong>What happens next:</strong> READY campaigns wait for an Android device (Phase 2). No SMS is sent,
              no delivery status is fabricated, and opted-out recipients stay excluded.
            </Alert>
          </CardBody>
        </Card>
      )}

      {/* Footer nav */}
      <div className="mt-6 flex items-center justify-between">
        <Button variant="ghost" onClick={() => setStep((current) => Math.max(0, current - 1))} disabled={step === 0}>
          <ArrowLeft className="h-4 w-4" /> Back
        </Button>
        {step < STEPS.length - 1 ? (
          <Button onClick={() => setStep((current) => Math.min(STEPS.length - 1, current + 1))} disabled={!canContinue}>
            Continue <ArrowRight className="h-4 w-4" />
          </Button>
        ) : (
          <Button variant="outline" onClick={() => navigate('/campaigns')}>
            <CheckCircle2 className="h-4 w-4" /> Done
          </Button>
        )}
      </div>
    </div>
  )
}

function SummaryStat({ label, value, tone = '' }: { label: string; value: number; tone?: string }) {
  return (
    <div className="rounded-lg border border-zinc-200 px-3 py-2.5 dark:border-zinc-700">
      <p className="text-[10px] font-semibold tracking-wide text-zinc-400 uppercase">{label}</p>
      <p className={cn('text-xl font-bold text-zinc-900 dark:text-zinc-100', tone)}>{value}</p>
    </div>
  )
}
