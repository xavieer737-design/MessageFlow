import { useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Loader2, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Button } from '../ui/Button'
import { Modal } from '../ui/Modal'
import { Alert } from './imports'
import { useToast } from '../ui/Toast'
import { getErrorMessage } from '../../lib/api'
import { devicesApi } from '../../services/api'
import type { Device, TestMessageResult } from '../../types'

/**
 * Send one test SMS through a connected device.
 *
 * The result shown here is the REAL result reported by the Android
 * device after its SmsManager call - never a simulated success.
 */
export function TestSmsModal({
  device,
  open,
  onClose,
}: {
  device: Device | null
  open: boolean
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const { success, error } = useToast()
  const [phone, setPhone] = useState('')
  const [message, setMessage] = useState('Hello from MessageFlow!')
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [sending, setSending] = useState(false)
  const [result, setResult] = useState<TestMessageResult | null>(null)
  const [phase, setPhase] = useState<'form' | 'waiting' | 'done'>('form')

  useEffect(() => {
    if (open) {
      setPhase('form')
      setResult(null)
      setConfirmOpen(false)
      setPhone('')
      setMessage('Hello from MessageFlow!')
    }
  }, [open])

  // Poll for the real result while waiting.
  useEffect(() => {
    if (phase !== 'waiting' || !device || !result) return
    const timer = window.setInterval(async () => {
      try {
        const current = await devicesApi.testMessageResult(device.id, result.message_id)
        if (current.status === 'SEND_SUCCESS' || current.status === 'SEND_FAILED') {
          setResult(current)
          setPhase('done')
          queryClient.invalidateQueries({ queryKey: ['devices'] })
          window.clearInterval(timer)
        }
      } catch {
        // keep polling
      }
    }, 2000)
    return () => window.clearInterval(timer)
  }, [phase, device, result, queryClient])

  const submit = async () => {
    if (!device) return
    setSending(true)
    try {
      const created = await devicesApi.testMessage(device.id, { phone, message })
      setResult(created)
      setPhase('waiting')
      success(`Test message sent to the device (${device.device_name}) — waiting for the real result`)
    } catch (err) {
      error(getErrorMessage(err, 'Could not send test message'))
    } finally {
      setSending(false)
    }
  }

  const successResult = result?.status === 'SEND_SUCCESS'

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Send Test SMS"
      description={device ? `One test SMS from ${device.device_name}` : undefined}
      size="md"
      footer={
        phase === 'form' ? (
          <>
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button onClick={() => setConfirmOpen(true)} disabled={!phone.trim() || !message.trim()}>
              Send test SMS
            </Button>
          </>
        ) : phase === 'waiting' ? (
          <Button variant="outline" onClick={onClose}>Close</Button>
        ) : (
          <Button onClick={onClose}>Done</Button>
        )
      }
    >
      {phase === 'form' && (
        <div className="space-y-4">
          <Alert tone="warning">
            <strong>Consent check:</strong> only send to a number you are allowed to message (e.g. your own or an
            explicitly consented recipient).
          </Alert>
          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">Recipient phone</label>
            <input
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              placeholder="+91 98765 43210"
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30 focus:outline-none dark:border-zinc-700 dark:bg-zinc-900"
            />
          </div>
          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">Message</label>
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              rows={3}
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30 focus:outline-none dark:border-zinc-700 dark:bg-zinc-900"
            />
            <p className="text-xs text-zinc-400">{message.length} characters</p>
          </div>
        </div>
      )}

      {phase === 'waiting' && (
        <div className="flex flex-col items-center py-8 text-center">
          <Loader2 className="h-8 w-8 animate-spin text-brand-500" />
          <h3 className="mt-3 text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            Waiting for the device result…
          </h3>
          <p className="mt-1 max-w-xs text-sm text-zinc-500">
            The Android phone is performing the real SMS operation. The status below only changes when the device
            reports the actual result.
          </p>
          <p className="mt-4 font-mono text-xs text-zinc-400">{result?.phone}</p>
        </div>
      )}

      {phase === 'done' && result && (
        <div className="flex flex-col items-center py-6 text-center">
          {successResult ? (
            <CheckCircle2 className="h-10 w-10 text-emerald-500" />
          ) : (
            <XCircle className="h-10 w-10 text-red-500" />
          )}
          <h3 className="mt-3 text-base font-semibold text-zinc-900 dark:text-zinc-100">
            {successResult ? 'SMS sent (device confirmed)' : 'SMS failed (device reported)'}
          </h3>
          <p className="mt-1 max-w-xs text-sm text-zinc-500">
            {successResult
              ? 'The Android device confirmed that SmsManager accepted the message.'
              : `The device reported a failure: ${result.error ?? 'unknown error'}`}
          </p>
          <div className="mt-4 w-full max-w-xs rounded-lg border border-zinc-200 bg-zinc-50/60 p-3 text-left dark:border-zinc-700 dark:bg-zinc-800/40">
            <p className="text-xs text-zinc-400">To: <span className="font-mono">{result.phone}</span></p>
            <p className="mt-1 line-clamp-2 text-xs text-zinc-600 dark:text-zinc-300">{message}</p>
            <p className="mt-2 text-xs text-zinc-400">Status: <span className="font-mono">{result.status}</span></p>
          </div>
        </div>
      )}

      {/* Confirmation step */}
      <Modal
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="Confirm test SMS"
        description="This sends one real SMS and may incur carrier charges."
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmOpen(false)}>Cancel</Button>
            <Button onClick={() => { setConfirmOpen(false); submit() }} loading={sending}>
              Confirm send
            </Button>
          </>
        }
      >
        <p className="text-sm text-zinc-600 dark:text-zinc-300">
          You are about to send <strong>one test SMS</strong> from{' '}
          <strong>{device?.device_name}</strong> to <span className="font-mono">{phone}</span>.
        </p>
      </Modal>
    </Modal>
  )
}
