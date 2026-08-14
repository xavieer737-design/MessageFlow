import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, Eye, FileText, Pencil, Plus, Trash2 } from 'lucide-react'
import { useRef, useState } from 'react'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { ConfirmDialog } from '../components/ui/Modal'
import { Modal } from '../components/ui/Modal'
import { Dropdown, DropdownItem } from '../components/ui/Dropdown'
import { EmptyState } from '../components/ui/EmptyState'
import { Field, Input, Textarea } from '../components/ui/Form'
import { PageHeader, Alert } from '../components/ui/Misc'
import { useToast } from '../components/ui/Toast'
import { getErrorMessage } from '../lib/api'
import { formatDate } from '../lib/format'
import { analyzeSms } from '../lib/smsCounter'
import { extractVariables, insertVariable, personalize, VARIABLE_LABELS, type TemplateVariable } from '../lib/templateVars'
import { templatesApi } from '../services/api'
import type { MessageTemplate } from '../types'
import { cn } from '../lib/cn'

const SAMPLE_VALUES = {
  first_name: 'Rahul',
  last_name: 'Sharma',
  phone: '+919876543210',
  email: 'rahul@example.com',
  company: 'ABC Ltd',
  notes: 'priority customer',
}

function SmsCounter({ text }: { text: string }) {
  const analysis = analyzeSms(text)
  return (
    <div className="flex flex-wrap items-center gap-3 text-xs text-zinc-500 dark:text-zinc-400">
      <span>
        Characters: <strong className="font-semibold text-zinc-800 dark:text-zinc-200">{analysis.characters}</strong>
      </span>
      <span>
        SMS segments: <strong className="font-semibold text-zinc-800 dark:text-zinc-200">{analysis.segments}</strong>
      </span>
      <Badge tone={analysis.encoding === 'GSM-7' ? 'gray' : 'violet'}>{analysis.encoding}</Badge>
      {analysis.truncated && (
        <span className="text-amber-600 dark:text-amber-400">
          ⚠ Splits into {analysis.segments} segments ({analysis.segments > 1 ? 'charged per segment' : ''})
        </span>
      )}
      {analysis.exceedLimit && (
        <span className="font-medium text-red-600 dark:text-red-400">
          Exceeds the practical 10-segment SMS limit — shorten the message.
        </span>
      )}
    </div>
  )
}

export function TemplatesPage() {
  const queryClient = useQueryClient()
  const { success, error } = useToast()

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<MessageTemplate | null>(null)
  const [name, setName] = useState('')
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<MessageTemplate | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [previewTarget, setPreviewTarget] = useState<MessageTemplate | null>(null)
  const [previewName, setPreviewName] = useState<string>('Rahul')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const { data: templates, isLoading, isError } = useQuery({ queryKey: ['templates'], queryFn: templatesApi.list })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['templates'] })
  }

  const openCreate = () => {
    setEditing(null)
    setName('')
    setMessage('')
    setModalOpen(true)
  }

  const openEdit = (template: MessageTemplate) => {
    setEditing(template)
    setName(template.name)
    setMessage(template.message)
    setModalOpen(true)
  }

  const save = async () => {
    if (!name.trim() || !message.trim()) return
    setSaving(true)
    try {
      if (editing) {
        await templatesApi.update(editing.id, { name: name.trim(), message })
        success('Template updated')
      } else {
        await templatesApi.create({ name: name.trim(), message })
        success('Template created')
      }
      setModalOpen(false)
      refresh()
    } catch (err) {
      error(getErrorMessage(err, 'Could not save template'))
    } finally {
      setSaving(false)
    }
  }

  const duplicate = async (template: MessageTemplate) => {
    try {
      await templatesApi.duplicate(template.id)
      success('Template duplicated')
      refresh()
    } catch (err) {
      error(getErrorMessage(err, 'Could not duplicate template'))
    }
  }

  const removeTemplate = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await templatesApi.remove(deleteTarget.id)
      success('Template deleted')
      refresh()
      setDeleteTarget(null)
    } catch (err) {
      error(getErrorMessage(err, 'Could not delete template'))
    } finally {
      setDeleting(false)
    }
  }

  const pickVariable = (variable: TemplateVariable) => {
    const textarea = textareaRef.current
    const cursor = textarea?.selectionStart ?? message.length
    setMessage(insertVariable(message, variable, cursor))
    requestAnimationFrame(() => {
      if (textarea) {
        textarea.focus()
        textarea.selectionStart = textarea.selectionEnd = cursor + variable.length + 4
      }
    })
  }

  const variables = extractVariables(message)
  const previewValues = { ...SAMPLE_VALUES, first_name: previewName }
  const preview = personalize(previewTarget?.message ?? '', previewValues)

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Message Templates"
        description={'Reusable, personalized message templates with {{variables}}.'}
        actions={
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4" /> New template
          </Button>
        }
      />

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-44 animate-pulse rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900" />
          ))}
        </div>
      ) : isError ? (
        <EmptyState title="Could not load templates" description="Check that the backend is running and try again." />
      ) : !templates || templates.length === 0 ? (
        <div className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
          <EmptyState
            icon={FileText}
            title="No templates yet"
            description={'Create templates with variables like {{first_name}} and {{company}} to personalize every message.'}
            action={<Button onClick={openCreate}><Plus className="h-4 w-4" /> New template</Button>}
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {templates.map((template) => (
            <div key={template.id} className="flex flex-col rounded-xl border border-zinc-200 bg-white p-5 shadow-card dark:border-zinc-800 dark:bg-zinc-900">
              <div className="flex items-start justify-between gap-2">
                <h3 className="truncate text-sm font-semibold text-zinc-900 dark:text-zinc-100">{template.name}</h3>
                <Dropdown>
                  {(close) => (
                    <>
                      <DropdownItem icon={<Eye className="h-4 w-4" />} onClick={() => { setPreviewTarget(template); close() }}>
                        Preview
                      </DropdownItem>
                      <DropdownItem icon={<Pencil className="h-4 w-4" />} onClick={() => { openEdit(template); close() }}>
                        Edit
                      </DropdownItem>
                      <DropdownItem icon={<Copy className="h-4 w-4" />} onClick={() => { duplicate(template); close() }}>
                        Duplicate
                      </DropdownItem>
                      <DropdownItem danger icon={<Trash2 className="h-4 w-4" />} onClick={() => { setDeleteTarget(template); close() }}>
                        Delete
                      </DropdownItem>
                    </>
                  )}
                </Dropdown>
              </div>
              <p className="mt-2 line-clamp-3 flex-1 font-mono text-xs leading-relaxed whitespace-pre-wrap text-zinc-600 dark:text-zinc-300">
                {template.message}
              </p>
              <div className="mt-3 flex items-center justify-between border-t border-zinc-100 pt-3 dark:border-zinc-800">
                <p className="text-xs text-zinc-400">Updated {formatDate(template.updated_at)}</p>
                <button
                  onClick={() => setPreviewTarget(template)}
                  className="text-xs font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400"
                >
                  Preview →
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Editor modal */}
      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? 'Edit template' : 'New template'}
        description={'Use {{variables}} to personalize each message.'}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button onClick={save} disabled={!name.trim() || !message.trim()} loading={saving}>
              {editing ? 'Save changes' : 'Create template'}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Template name" required>
            <Input value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. Order update" />
          </Field>
          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Message</span>
              <span className="text-xs text-zinc-400">Click a variable to insert it at the cursor</span>
            </div>
            <Textarea
              ref={textareaRef}
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              placeholder="Hi {{first_name}}, your order from {{company}} is ready."
              className="min-h-[140px] font-mono text-xs"
              rows={6}
            />
            <div className="mt-2 flex flex-wrap gap-1.5">
              {Object.entries(VARIABLE_LABELS).map(([variable, label]) => (
                <button
                  key={variable}
                  type="button"
                  onClick={() => pickVariable(variable as TemplateVariable)}
                  className="rounded-md border border-zinc-200 bg-zinc-50 px-2 py-1 font-mono text-[11px] text-zinc-600 transition-colors hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-brand-500/10"
                >
                  {`{{${variable}}}`}
                  <span className="ml-1 font-sans text-zinc-400">{label}</span>
                </button>
              ))}
            </div>
          </div>
          <SmsCounter text={message} />
          {variables.unsupported.length > 0 && (
            <Alert tone="error">
              Unsupported variables: {variables.unsupported.map((v) => `{{${v}}}`).join(', ')}. Supported: first_name,
              last_name, phone, email, company, notes.
            </Alert>
          )}
        </div>
      </Modal>

      {/* Preview modal */}
      <Modal
        open={!!previewTarget}
        onClose={() => setPreviewTarget(null)}
        title="Template preview"
        description="See how the message looks with real values."
        size="lg"
      >
        {previewTarget && (
          <div className="space-y-4">
            <Field label="Sample first name">
              <Input value={previewName} onChange={(event) => setPreviewName(event.target.value)} />
            </Field>
            <div>
              <p className="mb-1.5 text-xs font-semibold tracking-wide text-zinc-400 uppercase">Personalized preview</p>
              <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-700 dark:bg-zinc-800/40">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-xs font-medium text-zinc-500">From: MessageFlow · To: {previewName}</span>
                  <Badge tone="gray">SMS preview</Badge>
                </div>
                <p className="text-sm whitespace-pre-wrap text-zinc-800 dark:text-zinc-100">{preview.text || '(empty after personalization)'}</p>
              </div>
            </div>
            <SmsCounter text={preview.text} />
            {preview.missing.length > 0 && (
              <Alert tone="warning">
                Missing values for: {preview.missing.join(', ')} — they will appear blank for this recipient.
              </Alert>
            )}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {Object.entries(SAMPLE_VALUES).map(([key, value]) => (
                <div key={key} className={cn('rounded-lg border border-zinc-100 px-3 py-2 dark:border-zinc-800')}>
                  <p className="text-[10px] font-semibold tracking-wide text-zinc-400 uppercase">{key}</p>
                  <p className="truncate text-sm text-zinc-700 dark:text-zinc-200">{value}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={removeTemplate}
        loading={deleting}
        title="Delete template"
        message={<>Delete template <strong>{deleteTarget?.name}</strong>? Campaigns that already copied this text are unaffected.</>}
      />
    </div>
  )
}
