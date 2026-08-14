import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, FileSpreadsheet, Upload, XCircle } from 'lucide-react'
import { Button } from '../ui/Button'
import { Modal } from '../ui/Modal'
import { Alert, Spinner } from '../ui/Misc'
import { useToast } from '../ui/Toast'
import { getErrorMessage } from '../../lib/api'
import { contactsApi } from '../../services/api'
import type { ImportSummary, ImportUploadResponse } from '../../types'
import { cn } from '../../lib/cn'

const TARGET_OPTIONS = ['phone', 'first_name', 'last_name', 'email', 'company', 'notes', '__skip__'] as const

const TARGET_LABELS: Record<string, string> = {
  phone: 'Phone',
  first_name: 'First name',
  last_name: 'Last name',
  email: 'Email',
  company: 'Company',
  notes: 'Notes',
  __skip__: 'Skip column',
}

type Step = 'upload' | 'map' | 'preview' | 'done'

export function ImportWizard({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient()
  const { success, error } = useToast()
  const [step, setStep] = useState<Step>('upload')
  const [uploading, setUploading] = useState(false)
  const [data, setData] = useState<ImportUploadResponse | null>(null)
  const [mapping, setMapping] = useState<Record<string, string>>({})
  const [summary, setSummary] = useState<ImportSummary | null>(null)
  const [result, setResult] = useState<ImportSummary | null>(null)
  const [validatedRows, setValidatedRows] = useState<Array<{ row_number: number; values: Record<string, string>; status: string; errors: string[]; warnings: string[] }>>([])

  const reset = () => {
    setStep('upload')
    setData(null)
    setMapping({})
    setSummary(null)
    setResult(null)
    setValidatedRows([])
  }

  const close = () => {
    reset()
    onClose()
  }

  const pickFile = async (file: File | undefined | null) => {
    if (!file) return
    setUploading(true)
    try {
      const response = await contactsApi.importUpload(file)
      setData(response)
      setMapping(response.suggested_mapping)
      setSummary(response.summary)
      setStep('map')
    } catch (err) {
      error(getErrorMessage(err, 'Could not parse the file'))
    } finally {
      setUploading(false)
    }
  }

  const runValidation = async () => {
    if (!data) return
    try {
      const response = await contactsApi.importValidate(data.file_id, mapping)
      setSummary(response.summary)
      setValidatedRows(response.rows)
      setStep('preview')
    } catch (err) {
      error(getErrorMessage(err, 'Validation failed'))
    }
  }

  const confirmImport = async () => {
    if (!data) return
    try {
      const response = await contactsApi.importConfirm(data.file_id, mapping)
      setResult(response)
      setStep('done')
      queryClient.invalidateQueries({ queryKey: ['contacts'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      success(`${response.imported} contact${response.imported === 1 ? '' : 's'} imported`)
    } catch (err) {
      error(getErrorMessage(err, 'Import failed'))
    }
  }

  const fileHasPhone = Object.values(mapping).includes('phone')
  const mappingMissingPhone = step === 'map' && !fileHasPhone

  const steps = ['Upload', 'Map columns', 'Preview', 'Done']

  return (
    <Modal
      open={open}
      onClose={close}
      title="Import contacts"
      description="CSV and Excel (XLSX) files up to 10 MB"
      size="xl"
      footer={
        step === 'map' ? (
          <>
            <Button variant="ghost" onClick={() => setStep('upload')}>Back</Button>
            <Button onClick={runValidation} disabled={mappingMissingPhone}>Preview & validate</Button>
          </>
        ) : step === 'preview' ? (
          <>
            <Button variant="ghost" onClick={() => setStep('map')}>Back</Button>
            <Button onClick={confirmImport}>Import valid contacts</Button>
          </>
        ) : step === 'done' ? (
          <Button onClick={close}>Done</Button>
        ) : undefined
      }
    >
      {/* Stepper */}
      <div className="mb-5 flex items-center gap-1">
        {steps.map((label, index) => (
          <div key={label} className="flex flex-1 items-center gap-1">
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  'flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold',
                  index < ['upload', 'map', 'preview', 'done'].indexOf(step)
                    ? 'bg-emerald-500 text-white'
                    : index === ['upload', 'map', 'preview', 'done'].indexOf(step)
                      ? 'bg-brand-600 text-white'
                      : 'bg-zinc-200 text-zinc-500 dark:bg-zinc-700 dark:text-zinc-400',
                )}
              >
                {index < ['upload', 'map', 'preview', 'done'].indexOf(step) ? <CheckCircle2 className="h-3.5 w-3.5" /> : index + 1}
              </span>
              <span className={cn('text-xs font-medium', index === ['upload', 'map', 'preview', 'done'].indexOf(step) ? 'text-zinc-900 dark:text-zinc-100' : 'text-zinc-400')}>
                {label}
              </span>
            </div>
            {index < steps.length - 1 && <div className="mx-2 h-px flex-1 bg-zinc-200 dark:bg-zinc-700" />}
          </div>
        ))}
      </div>

      {step === 'upload' && (
        <div>
          <label
            className={cn(
              'flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-12 text-center transition-colors',
              'border-zinc-300 hover:border-brand-400 hover:bg-brand-50/40 dark:border-zinc-700 dark:hover:bg-brand-500/5',
            )}
          >
            <FileSpreadsheet className="h-8 w-8 text-zinc-400" />
            <span className="mt-3 text-sm font-medium text-zinc-700 dark:text-zinc-200">
              Drop your CSV or XLSX here, or click to browse
            </span>
            <span className="mt-1 text-xs text-zinc-400">
              Columns like phone, name, company and email are detected automatically.
            </span>
            <input
              type="file"
              accept=".csv,.xlsx"
              className="hidden"
              onChange={(event) => pickFile(event.target.files?.[0])}
              disabled={uploading}
            />
          </label>
          {uploading && (
            <div className="mt-4 flex items-center justify-center gap-2 text-sm text-zinc-500">
              <Spinner className="h-4 w-4" /> Parsing file…
            </div>
          )}
          <div className="mt-4">
            <Alert tone="info">
              <strong>Example CSV:</strong>
              <pre className="mt-1.5 overflow-x-auto rounded-md bg-white/70 p-2 text-xs dark:bg-zinc-900/50">
                {`phone,name,company,email\n9876543210,Rahul,ABC Ltd,rahul@example.com\n9876543211,Amit,XYZ Ltd,amit@example.com`}
              </pre>
            </Alert>
          </div>
        </div>
      )}

      {step === 'map' && data && (
        <div className="space-y-4">
          {mappingMissingPhone && (
            <Alert tone="warning">No column is mapped to Phone. Map a column to Phone before importing.</Alert>
          )}
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            We detected <strong className="text-zinc-800 dark:text-zinc-100">{data.columns.length}</strong> column
            {data.columns.length === 1 ? '' : 's'} in <strong className="text-zinc-800 dark:text-zinc-100">{data.filename}</strong>{' '}
            ({data.total_rows} rows). Review how each column is mapped:
          </p>
          <div className="overflow-hidden rounded-lg border border-zinc-200 dark:border-zinc-700">
            {data.columns.map((column, index) => (
              <div
                key={column}
                className={cn(
                  'flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between',
                  index % 2 === 0 ? 'bg-zinc-50/60 dark:bg-zinc-800/30' : 'bg-white dark:bg-zinc-900',
                )}
              >
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-medium text-zinc-800 dark:text-zinc-100">{column}</span>
                  {data.suggested_mapping[column] === 'first_name' && (
                    <span className="rounded-full bg-brand-50 px-2 py-0.5 text-[10px] font-semibold text-brand-700 dark:bg-brand-500/10 dark:text-brand-300">
                      suggested: first name
                    </span>
                  )}
                </div>
                <select
                  value={mapping[column] ?? '__skip__'}
                  onChange={(event) => setMapping({ ...mapping, [column]: event.target.value })}
                  className="h-8 w-full rounded-lg border border-zinc-300 bg-white px-2 text-xs text-zinc-800 focus:border-brand-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 sm:w-48"
                >
                  {TARGET_OPTIONS.map((target) => (
                    <option key={target} value={target}>
                      {TARGET_LABELS[target]}
                      {target === 'phone' ? ' *' : ''}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>
          {data.sample_rows.length > 0 && (
            <div>
              <p className="mb-1.5 text-xs font-medium text-zinc-500">Sample rows</p>
              <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-700">
                <table className="w-full text-xs">
                  <tbody>
                    {data.sample_rows.map((row, rowIndex) => (
                      <tr key={rowIndex} className="border-b border-zinc-100 last:border-0 dark:border-zinc-800">
                        {data.columns.map((column) => (
                          <td key={column} className="max-w-40 truncate px-3 py-1.5 text-zinc-600 dark:text-zinc-300">
                            {row[column] || <span className="text-zinc-300 dark:text-zinc-600">—</span>}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          {summary && <SummaryBar summary={summary} />}
        </div>
      )}

      {step === 'preview' && summary && (
        <div className="space-y-4">
          <SummaryBar summary={summary} />
          {summary.invalid > 0 && (
            <Alert tone="warning">
              {summary.invalid} row{summary.invalid === 1 ? '' : 's'} will be skipped because of invalid phone numbers
              or missing values. Nothing is silently discarded.
            </Alert>
          )}
          {summary.duplicates > 0 && (
            <Alert tone="warning">
              {summary.duplicates} duplicate{summary.duplicates === 1 ? '' : 's'} (already in your contacts or repeated in the file) will be skipped.
            </Alert>
          )}
          {summary.opted_out > 0 && (
            <Alert tone="warning">
              {summary.opted_out} number{summary.opted_out === 1 ? '' : 's'} on your opt-out list will not be imported.
            </Alert>
          )}
          {validatedRows.length > 0 && (
            <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-700">
              <table className="w-full min-w-[560px] text-xs">
                <thead>
                  <tr className="border-b border-zinc-200 bg-zinc-50 text-left dark:border-zinc-700 dark:bg-zinc-800/40">
                    <th className="px-3 py-2 font-semibold text-zinc-500">Row</th>
                    <th className="px-3 py-2 font-semibold text-zinc-500">Values</th>
                    <th className="px-3 py-2 font-semibold text-zinc-500">Status</th>
                    <th className="px-3 py-2 font-semibold text-zinc-500">Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {validatedRows.map((row) => (
                    <tr key={row.row_number} className="border-b border-zinc-100 last:border-0 dark:border-zinc-800">
                      <td className="px-3 py-2 text-zinc-500">{row.row_number}</td>
                      <td className="max-w-64 truncate px-3 py-2 text-zinc-700 dark:text-zinc-300">
                        {Object.entries(row.values)
                          .filter(([, value]) => value)
                          .map(([key, value]) => `${key}: ${value}`)
                          .join(' · ') || '—'}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={cn(
                            'rounded-full px-2 py-0.5 font-semibold',
                            row.status === 'valid' && 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400',
                            row.status === 'invalid' && 'bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-400',
                            (row.status === 'duplicate' || row.status === 'opted_out') && 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400',
                          )}
                        >
                          {row.status.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-zinc-500">{row.errors.join('; ') || row.warnings.join('; ') || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {step === 'done' && result && (
        <div className="flex flex-col items-center py-6 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400">
            <CheckCircle2 className="h-6 w-6" />
          </div>
          <h3 className="mt-3 text-base font-semibold text-zinc-900 dark:text-zinc-100">Import complete</h3>
          <div className="mt-4 grid w-full max-w-sm grid-cols-2 gap-3">
            <ResultStat label="Imported" value={result.imported ?? 0} tone="text-emerald-600" />
            <ResultStat label="Total rows" value={result.total} />
            <ResultStat label="Invalid" value={result.invalid} tone={result.invalid ? 'text-red-600' : ''} />
            <ResultStat label="Duplicates" value={result.duplicates} tone={result.duplicates ? 'text-amber-600' : ''} />
          </div>
          {result.opted_out > 0 && (
            <p className="mt-4 flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-400">
              <XCircle className="h-3.5 w-3.5" /> {result.opted_out} opted-out number{result.opted_out === 1 ? '' : 's'} excluded
            </p>
          )}
        </div>
      )}
    </Modal>
  )
}

function SummaryBar({ summary }: { summary: ImportSummary }) {
  const items = [
    { label: 'Total', value: summary.total, className: 'text-zinc-900 dark:text-zinc-100' },
    { label: 'Valid', value: summary.valid, className: 'text-emerald-600 dark:text-emerald-400' },
    { label: 'Invalid', value: summary.invalid, className: 'text-red-600 dark:text-red-400' },
    { label: 'Duplicates', value: summary.duplicates, className: 'text-amber-600 dark:text-amber-400' },
    { label: 'Opted out', value: summary.opted_out, className: 'text-amber-600 dark:text-amber-400' },
  ]
  return (
    <div className="flex flex-wrap gap-3 rounded-lg border border-zinc-200 bg-zinc-50/60 px-4 py-3 dark:border-zinc-700 dark:bg-zinc-800/30">
      {items.map((item) => (
        <div key={item.label}>
          <p className="text-[10px] font-semibold tracking-wide text-zinc-400 uppercase">{item.label}</p>
          <p className={`text-lg font-bold ${item.className}`}>{item.value}</p>
        </div>
      ))}
    </div>
  )
}

function ResultStat({ label, value, tone = '' }: { label: string; value: number; tone?: string }) {
  return (
    <div className="rounded-lg border border-zinc-200 px-3 py-2.5 dark:border-zinc-700">
      <p className="text-[10px] font-semibold tracking-wide text-zinc-400 uppercase">{label}</p>
      <p className={`text-xl font-bold ${tone || 'text-zinc-900 dark:text-zinc-100'}`}>{value}</p>
    </div>
  )
}

export function UploadIcon() {
  return <Upload className="h-4 w-4" />
}
