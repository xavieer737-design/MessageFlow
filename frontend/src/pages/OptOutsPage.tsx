import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, PhoneOff, Plus, Trash2, Upload } from 'lucide-react'
import { Card, CardBody } from '../components/ui/Card'
import { useState } from 'react'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { ConfirmDialog } from '../components/ui/Modal'
import { Modal } from '../components/ui/Modal'
import { EmptyState } from '../components/ui/EmptyState'
import { Field, Input, Textarea } from '../components/ui/Form'
import { PageHeader, SearchInput, useDebouncedValue, Alert } from '../components/ui/Misc'
import { Pagination, Table, Td, Th, THead, TRow } from '../components/ui/Table'
import { useToast } from '../components/ui/Toast'
import { getErrorMessage } from '../lib/api'
import { formatDate } from '../lib/format'
import { optoutsApi } from '../services/api'

const PAGE_SIZE = 25

export function OptOutsPage() {
  const queryClient = useQueryClient()
  const { success, error } = useToast()

  const [search, setSearch] = useState('')
  const debouncedSearch = useDebouncedValue(search, 300)
  const [page, setPage] = useState(1)

  const [addOpen, setAddOpen] = useState(false)
  const [phone, setPhone] = useState('')
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)

  const [bulkOpen, setBulkOpen] = useState(false)
  const [bulkText, setBulkText] = useState('')
  const [bulkResult, setBulkResult] = useState<{ imported: number; duplicates: number; skipped_invalid: string[] } | null>(null)

  const [deleteTarget, setDeleteTarget] = useState<{ id: number; phone: string } | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [importing, setImporting] = useState(false)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['optouts', { debouncedSearch, page }],
    queryFn: () => optoutsApi.list({ search: debouncedSearch, page, page_size: PAGE_SIZE }),
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['optouts'] })
    queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    queryClient.invalidateQueries({ queryKey: ['contacts'] })
  }

  const addOptOut = async () => {
    setSaving(true)
    try {
      await optoutsApi.create({ phone: phone.trim(), reason: reason.trim() || undefined })
      success('Number added to the opt-out list')
      setPhone('')
      setReason('')
      setAddOpen(false)
      refresh()
    } catch (err) {
      error(getErrorMessage(err, 'Could not add number'))
    } finally {
      setSaving(false)
    }
  }

  const runBulk = async () => {
    const phones = bulkText.split(/[\n,;]+/).map((p) => p.trim()).filter(Boolean)
    if (phones.length === 0) return
    try {
      const result = await optoutsApi.bulk(phones)
      setBulkResult(result)
      refresh()
    } catch (err) {
      error(getErrorMessage(err, 'Could not add numbers'))
    }
  }

  const importFile = async (file: File | undefined | null) => {
    if (!file) return
    setImporting(true)
    try {
      const form = new FormData()
      form.append('file', file)
      const result = await fetch('/api/optouts/import', {
        method: 'POST',
        credentials: 'include',
        body: form,
      }).then(async (response) => {
        const body = await response.json()
        if (!response.ok) throw new Error(body.detail ?? 'Import failed')
        return body as { imported: number; duplicates: number; skipped_invalid: string[] }
      })
      setBulkResult(result)
      refresh()
    } catch (err) {
      error(getErrorMessage(err, 'Could not import file'))
    } finally {
      setImporting(false)
    }
  }

  const removeOptOut = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await optoutsApi.remove(deleteTarget.id)
      success('Number removed from the opt-out list')
      refresh()
      setDeleteTarget(null)
    } catch (err) {
      error(getErrorMessage(err, 'Could not remove number'))
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Opt-out List"
        description="Numbers that must never receive messages. Campaign validation excludes them automatically."
        actions={
          <>
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-zinc-300 bg-white px-3.5 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800">
              <Upload className="h-4 w-4" /> Import numbers
              <input
                type="file"
                accept=".csv,.xlsx"
                className="hidden"
                onChange={(event) => importFile(event.target.files?.[0])}
                disabled={importing}
              />
            </label>
            <Button variant="outline" onClick={() => setBulkOpen(true)}>
              <Plus className="h-4 w-4" /> Add many
            </Button>
            <Button onClick={() => setAddOpen(true)}>
              <Plus className="h-4 w-4" /> Add number
            </Button>
          </>
        }
      />

      <Card className="mb-5">
        <CardBody>
          <Alert tone="info">
            <strong>How opt-outs work:</strong> numbers here are excluded from every campaign at validation time, and
            imports skip them too. The system is ready for future STOP / UNSUBSCRIBE keyword processing from replies.
          </Alert>
        </CardBody>
      </Card>

      <div className="mb-4">
        <SearchInput value={search} onChange={setSearch} placeholder="Search phone numbers…" className="w-full sm:w-72" />
      </div>

      <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-card dark:border-zinc-800 dark:bg-zinc-900">
        {isLoading ? (
          <div className="animate-pulse">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex gap-4 border-b border-zinc-100 px-5 py-4 dark:border-zinc-800">
                <div className="h-3.5 w-40 rounded bg-zinc-100 dark:bg-zinc-800" />
                <div className="h-3.5 w-48 rounded bg-zinc-100 dark:bg-zinc-800" />
                <div className="ml-auto h-3.5 w-16 rounded bg-zinc-100 dark:bg-zinc-800" />
              </div>
            ))}
          </div>
        ) : isError ? (
          <EmptyState title="Could not load opt-outs" description="Check that the backend is running and try again." />
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            icon={PhoneOff}
            title={debouncedSearch ? 'No numbers match your search' : 'No opt-outs yet'}
            description={
              debouncedSearch
                ? 'Try a different search term.'
                : 'Add numbers that have asked not to be contacted. They will be excluded from every campaign.'
            }
            action={
              debouncedSearch ? undefined : (
                <Button onClick={() => setAddOpen(true)}><Plus className="h-4 w-4" /> Add number</Button>
              )
            }
          />
        ) : (
          <>
            <Table>
              <THead>
                <tr className="border-b border-zinc-200 bg-zinc-50/80 dark:border-zinc-800 dark:bg-zinc-800/40">
                  <Th>Phone</Th>
                  <Th>Reason</Th>
                  <Th>Added</Th>
                  <Th className="w-14" />
                </tr>
              </THead>
              <tbody>
                {data.items.map((entry) => (
                  <TRow key={entry.id}>
                    <Td>
                      <span className="font-mono text-sm">{entry.phone}</span>
                      <Badge tone="red" className="ml-2">opted out</Badge>
                    </Td>
                    <Td className="max-w-72 truncate">{entry.reason ?? '—'}</Td>
                    <Td className="text-xs whitespace-nowrap">{formatDate(entry.created_at)}</Td>
                    <Td>
                      <button
                        onClick={() => setDeleteTarget({ id: entry.id, phone: entry.phone })}
                        className="rounded-lg p-1.5 text-zinc-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10"
                        aria-label={`Remove ${entry.phone}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </Td>
                  </TRow>
                ))}
              </tbody>
            </Table>
            <Pagination page={data.page} pages={data.pages} total={data.total} onChange={setPage} />
          </>
        )}
      </div>

      <div className="mt-4 flex justify-end">
        <a
          href={optoutsApi.exportUrl()}
          className="inline-flex items-center gap-2 rounded-lg border border-zinc-300 bg-white px-3.5 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
        >
          <Download className="h-4 w-4" /> Export CSV
        </a>
      </div>

      {/* Single add modal */}
      <Modal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title="Add opt-out number"
        description="This number will never receive campaign messages."
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setAddOpen(false)}>Cancel</Button>
            <Button onClick={addOptOut} disabled={!phone.trim()} loading={saving}>Add number</Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Phone" required hint="International format is stored automatically">
            <Input value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="+91 98765 43210" />
          </Field>
          <Field label="Reason">
            <Textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="e.g. STOP request, complained" />
          </Field>
        </div>
      </Modal>

      {/* Bulk add modal */}
      <Modal
        open={bulkOpen}
        onClose={() => { setBulkOpen(false); setBulkResult(null); setBulkText('') }}
        title="Add opt-out numbers"
        description="One number per line (commas and semicolons also work)."
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={() => { setBulkOpen(false); setBulkResult(null); setBulkText('') }}>Close</Button>
            {!bulkResult && <Button onClick={runBulk} disabled={!bulkText.trim()}>Add numbers</Button>}
          </>
        }
      >
        {bulkResult ? (
          <div className="space-y-3">
            <Alert tone="success">
              <strong>{bulkResult.imported}</strong> number{bulkResult.imported === 1 ? '' : 's'} added ·{' '}
              {bulkResult.duplicates} duplicate{bulkResult.duplicates === 1 ? '' : 's'} skipped
            </Alert>
            {bulkResult.skipped_invalid.length > 0 && (
              <Alert tone="warning">
                Invalid numbers not added: {bulkResult.skipped_invalid.join(', ')}
              </Alert>
            )}
          </div>
        ) : (
          <Textarea
            value={bulkText}
            onChange={(event) => setBulkText(event.target.value)}
            placeholder={'9876543210\n9876543211\n+44 20 7946 0958'}
            className="min-h-[140px] font-mono text-xs"
          />
        )}
      </Modal>

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={removeOptOut}
        loading={deleting}
        title="Remove from opt-out list"
        message={<>Remove <strong>{deleteTarget?.phone}</strong> from the opt-out list? It could receive messages again in future campaigns.</>}
      />
    </div>
  )
}
