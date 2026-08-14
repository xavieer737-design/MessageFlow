import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Battery,
  BatteryLow,
  BatteryMedium,
  BatteryFull,
  Info,
  Plus,
  Send,
  Signal,
  Smartphone,
  Trash2,
  Unplug,
  Wifi,
} from 'lucide-react'
import { useState } from 'react'
import { PairingModal } from '../components/devices/PairingModal'
import { TestSmsModal } from '../components/devices/TestSmsModal'
import { StatusBadge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardBody } from '../components/ui/Card'
import { ConfirmDialog } from '../components/ui/Modal'
import { EmptyState } from '../components/ui/EmptyState'
import { PageHeader, Alert } from '../components/ui/Misc'
import { useToast } from '../components/ui/Toast'
import { getErrorMessage } from '../lib/api'
import { formatDateTime, timeAgo } from '../lib/format'
import { devicesApi } from '../services/api'
import type { Device } from '../types'

function BatteryIcon({ level }: { level: number | null }) {
  if (level === null) return <Battery className="h-4 w-4 text-zinc-400" />
  if (level < 20) return <BatteryLow className="h-4 w-4 text-red-500" />
  if (level < 60) return <BatteryMedium className="h-4 w-4 text-amber-500" />
  return <BatteryFull className="h-4 w-4 text-emerald-500" />
}

export function DevicesPage() {
  const queryClient = useQueryClient()
  const { success, error } = useToast()

  const [pairingOpen, setPairingOpen] = useState(false)
  const [deviceIdentifier] = useState(() => `mf-${crypto.randomUUID().replace(/-/g, '').slice(0, 20)}`)
  const [testDevice, setTestDevice] = useState<Device | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Device | null>(null)
  const [disconnectTarget, setDisconnectTarget] = useState<Device | null>(null)
  const [deleting, setDeleting] = useState(false)

  const { data: devices, isLoading, isError } = useQuery({
    queryKey: ['devices'],
    queryFn: devicesApi.list,
    refetchInterval: 5000, // keep "last seen" fresh
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['devices'] })
    queryClient.invalidateQueries({ queryKey: ['dashboard'] })
  }

  const removeDevice = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await devicesApi.remove(deleteTarget.id)
      success('Device removed')
      refresh()
      setDeleteTarget(null)
    } catch (err) {
      error(getErrorMessage(err, 'Could not remove device'))
    } finally {
      setDeleting(false)
    }
  }

  const disconnectDevice = async () => {
    if (!disconnectTarget) return
    setDeleting(true)
    try {
      await devicesApi.disconnect(disconnectTarget.id)
      success(`Device "${disconnectTarget.device_name}" disconnected`)
      refresh()
      setDisconnectTarget(null)
    } catch (err) {
      error(getErrorMessage(err, 'Could not disconnect device'))
    } finally {
      setDeleting(false)
    }
  }

  const connectedCount = devices?.filter((d) => d.connection_status === 'CONNECTED' || d.is_online).length ?? 0

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Devices"
        description="Your Android phones that send campaigns through their own SIM."
        actions={
          <Button onClick={() => setPairingOpen(true)}>
            <Plus className="h-4 w-4" /> Connect Android Device
          </Button>
        }
      />

      {connectedCount === 0 && devices && devices.length > 0 && (
        <Card className="mb-5">
          <CardBody>
            <Alert tone="info">
              <strong>No device is online right now.</strong> Devices marked OFFLINE re-connect automatically when the
              Android app is reachable. Campaigns on a disconnected device stay paused and resume safely on reconnect.
            </Alert>
          </CardBody>
        </Card>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {[1, 2].map((i) => (
            <div key={i} className="h-48 animate-pulse rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900" />
          ))}
        </div>
      ) : isError ? (
        <EmptyState title="Could not load devices" description="Check that the backend is running and try again." />
      ) : !devices || devices.length === 0 ? (
        <div className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
          <EmptyState
            icon={Smartphone}
            title="No Android device connected"
            description="Pair your Android phone to start sending messages. The phone sends SMS through its own SIM using Android's official SMS API."
            action={
              <Button onClick={() => setPairingOpen(true)}>
                <Plus className="h-4 w-4" /> Connect Android Device
              </Button>
            }
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {devices.map((device) => (
            <Card key={device.id} className="flex flex-col p-5">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
                    <Smartphone className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{device.device_name}</h3>
                    <p className="text-xs text-zinc-400">{device.phone_model ?? 'Model unknown'}</p>
                  </div>
                </div>
                <StatusBadge status={device.connection_status} />
              </div>

              <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
                <Metric icon={<BatteryIcon level={device.battery_level} />} label="Battery" value={device.battery_level !== null ? `${device.battery_level}%` : '—'} />
                <Metric icon={<Signal className="h-4 w-4 text-zinc-400" />} label="SIM" value={device.sim_state ?? '—'} />
                <Metric icon={<Wifi className="h-4 w-4 text-zinc-400" />} label="Network" value={device.network_state ?? '—'} />
                <Metric icon={<Info className="h-4 w-4 text-zinc-400" />} label="Android" value={device.android_version ?? '—'} />
              </div>

              <div className="mt-3 flex items-center justify-between border-t border-zinc-100 pt-3 text-xs dark:border-zinc-800">
                <span className="text-zinc-400">
                  {device.is_online ? 'Connected' : device.last_seen ? `Last seen ${timeAgo(device.last_seen)}` : 'Never seen'}
                </span>
                {device.paired_at && <span className="text-zinc-400">Paired {formatDateTime(device.paired_at)}</span>}
              </div>

              <div className="mt-3 grid grid-cols-3 gap-2 rounded-lg bg-zinc-50 p-2.5 text-center dark:bg-zinc-800/40">
                <Counter label="Queued" value={device.messages_queued} />
                <Counter label="Sent" value={device.messages_sent} tone="text-emerald-600" />
                <Counter label="Failed" value={device.messages_failed} tone={device.messages_failed ? 'text-red-600' : ''} />
              </div>

              <div className="mt-4 flex items-center justify-end gap-1.5 border-t border-zinc-100 pt-3 dark:border-zinc-800">
                <button
                  onClick={() => setTestDevice(device)}
                  disabled={!device.is_online}
                  className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-zinc-600 transition-colors hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-40 dark:text-zinc-300 dark:hover:bg-zinc-800"
                  title={device.is_online ? 'Send one test SMS' : 'Device must be connected'}
                >
                  <Send className="h-3.5 w-3.5" /> Test SMS
                </button>
                {device.connection_status === 'CONNECTED' && (
                  <button
                    onClick={() => setDisconnectTarget(device)}
                    className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-zinc-600 transition-colors hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
                  >
                    <Unplug className="h-3.5 w-3.5" /> Disconnect
                  </button>
                )}
                <button
                  onClick={() => setDeleteTarget(device)}
                  className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-red-600 transition-colors hover:bg-red-50 dark:hover:bg-red-500/10"
                >
                  <Trash2 className="h-3.5 w-3.5" /> Remove
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <PairingModal
        open={pairingOpen}
        onClose={() => setPairingOpen(false)}
        deviceIdentifier={deviceIdentifier}
        onPaired={refresh}
      />
      <TestSmsModal device={testDevice} open={!!testDevice} onClose={() => setTestDevice(null)} />

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={removeDevice}
        loading={deleting}
        title="Remove device"
        message={<>Remove <strong>{deleteTarget?.device_name}</strong> from your account? It can be paired again later.</>}
      />
      <ConfirmDialog
        open={!!disconnectTarget}
        onClose={() => setDisconnectTarget(null)}
        onConfirm={disconnectDevice}
        loading={deleting}
        title="Disconnect device"
        message={<>Disconnect <strong>{disconnectTarget?.device_name}</strong>? Active campaigns on this device will pause and resume safely when it reconnects.</>}
      />
    </div>
  )
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center gap-1.5 text-zinc-500 dark:text-zinc-400">
      {icon}
      <span className="text-zinc-400">{label}</span>
      <span className="ml-auto font-medium text-zinc-700 dark:text-zinc-200">{value}</span>
    </div>
  )
}

function Counter({ label, value, tone = '' }: { label: string; value: number; tone?: string }) {
  return (
    <div>
      <p className={`text-sm font-bold ${tone || 'text-zinc-800 dark:text-zinc-100'}`}>{value}</p>
      <p className="text-[10px] font-semibold tracking-wide text-zinc-400 uppercase">{label}</p>
    </div>
  )
}
