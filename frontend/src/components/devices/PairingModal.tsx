import { useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, QrCode, Timer, XCircle } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import QRCode from 'qrcode'
import { Button } from '../ui/Button'
import { Modal } from '../ui/Modal'
import { Alert, Spinner } from '../ui/Misc'
import { useToast } from '../ui/Toast'
import { getErrorMessage } from '../../lib/api'
import { devicesApi } from '../../services/api'
import type { Device } from '../../types'

/**
 * QR pairing modal.
 *
 * Flow: start a pairing session -> show QR (contains only a short-lived
 * one-time token + server URL) -> poll the session until the Android app
 * completes the pairing -> show the paired device.
 */
export function PairingModal({
  open,
  onClose,
  deviceIdentifier,
  onPaired,
}: {
  open: boolean
  onClose: () => void
  deviceIdentifier: string
  onPaired: (device: Device) => void
}) {
  const queryClient = useQueryClient()
  const { success, error } = useToast()
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [qrDataUrl, setQrDataUrl] = useState<string | null>(null)
  const [expiresAt, setExpiresAt] = useState<string | null>(null)
  const [status, setStatus] = useState<'starting' | 'pending' | 'expired' | 'paired'>('starting')
  const [pairedDevice, setPairedDevice] = useState<Device | null>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const start = async () => {
    setStatus('starting')
    try {
      const pairing = await devicesApi.pairingStart({
        device_name: 'Android device',
        device_identifier: deviceIdentifier,
      })
      setSessionId(pairing.session_id)
      setExpiresAt(pairing.expires_at)
      const url = await QRCode.toDataURL(pairing.qr_payload, {
        width: 240,
        margin: 2,
        color: { dark: '#18181b', light: '#ffffff' },
      })
      setQrDataUrl(url)
      setStatus('pending')
    } catch (err) {
      error(getErrorMessage(err, 'Could not start pairing'))
      setStatus('starting')
    }
  }

  // Poll the pairing session while open and pending.
  useEffect(() => {
    if (!open) return
    if (sessionId === null || status !== 'pending') return
    const timer = window.setInterval(async () => {
      try {
        const result = await devicesApi.pairingStatus(sessionId)
        if (result.status === 'paired' && result.device) {
          setStatus('paired')
          setPairedDevice(result.device)
          queryClient.invalidateQueries({ queryKey: ['devices'] })
          queryClient.invalidateQueries({ queryKey: ['dashboard'] })
          success(`Device "${result.device.device_name}" paired`)
          onPaired(result.device)
          window.clearInterval(timer)
        } else if (result.status === 'expired') {
          setStatus('expired')
          window.clearInterval(timer)
        }
      } catch {
        // transient polling errors are ignored; the next tick retries
      }
    }, 2500)
    return () => window.clearInterval(timer)
  }, [open, sessionId, status, queryClient, success, onPaired])

  // Reset when the modal opens.
  useEffect(() => {
    if (open) {
      setStatus('starting')
      setSessionId(null)
      setQrDataUrl(null)
      setPairedDevice(null)
      start()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const secondsLeft = expiresAt
    ? Math.max(0, Math.floor((new Date(expiresAt).getTime() - Date.now()) / 1000))
    : 0

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Connect Android Device"
      description="Scan the QR code with the MessageFlow Android app"
      size="md"
      footer={
        status === 'paired' ? (
          <Button onClick={onClose}>Done</Button>
        ) : (
          <>
            {status !== 'starting' && (
              <Button variant="ghost" onClick={() => { setStatus('starting'); start() }}>
                New QR code
              </Button>
            )}
            <Button variant="outline" onClick={onClose}>Close</Button>
          </>
        )
      }
    >
      {status === 'starting' && (
        <div className="flex flex-col items-center py-10">
          <Spinner className="h-6 w-6" />
          <p className="mt-3 text-sm text-zinc-500">Creating a secure pairing session…</p>
        </div>
      )}

      {status === 'pending' && qrDataUrl && (
        <div className="flex flex-col items-center">
          <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-700">
            <img src={qrDataUrl} alt="Pairing QR code" className="h-56 w-56" />
          </div>
          <div className="mt-4 flex items-center gap-1.5 text-xs text-zinc-400">
            <Timer className="h-3.5 w-3.5" />
            Token expires in {Math.floor(secondsLeft / 60)}m {secondsLeft % 60}s — single use only
          </div>
          <div className="mt-4 w-full">
            <Alert tone="info">
              <strong>On your phone:</strong> open the MessageFlow app → <em>Connect to Dashboard</em> → scan this QR
              code. The code contains only a short-lived pairing token — never your password or keys.
            </Alert>
          </div>
        </div>
      )}

      {status === 'expired' && (
        <div className="flex flex-col items-center py-6 text-center">
          <XCircle className="h-10 w-10 text-amber-500" />
          <h3 className="mt-3 text-sm font-semibold text-zinc-900 dark:text-zinc-100">Pairing token expired</h3>
          <p className="mt-1 text-sm text-zinc-500">Generate a new QR code and try again.</p>
        </div>
      )}

      {status === 'paired' && pairedDevice && (
        <div className="flex flex-col items-center py-4 text-center">
          <CheckCircle2 className="h-10 w-10 text-emerald-500" />
          <h3 className="mt-3 text-base font-semibold text-zinc-900 dark:text-zinc-100">✓ Device paired</h3>
          <div className="mt-4 w-full max-w-xs space-y-2 rounded-lg border border-zinc-200 bg-zinc-50/60 p-4 dark:border-zinc-700 dark:bg-zinc-800/40">
            <PairRow label="Device name" value={pairedDevice.device_name} />
            <PairRow label="Phone model" value={pairedDevice.phone_model ?? '—'} />
            <PairRow label="Android version" value={pairedDevice.android_version ?? '—'} />
          </div>
          <p className="mt-3 text-xs text-zinc-400">
            The device will appear as CONNECTED once the app establishes its secure connection.
          </p>
        </div>
      )}

      <div className="hidden">
        <QrCode />
        <canvas ref={canvasRef} />
      </div>
    </Modal>
  )
}

function PairRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-xs font-medium text-zinc-400">{label}</span>
      <span className="truncate text-sm font-medium text-zinc-800 dark:text-zinc-100">{value}</span>
    </div>
  )
}
