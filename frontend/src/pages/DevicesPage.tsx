import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Info, Plus, Smartphone, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { StatusBadge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardBody } from '../components/ui/Card'
import { ConfirmDialog } from '../components/ui/Modal'
import { Modal } from '../components/ui/Modal'
import { EmptyState } from '../components/ui/EmptyState'
import { PageHeader, Alert } from '../components/ui/Misc'
import { useToast } from '../components/ui/Toast'
import { getErrorMessage } from '../lib/api'
import { formatDateTime, timeAgo } from '../lib/format'
import { devicesApi } from '../services/api'
import type { Device } from '../types'

export function DevicesPage() {
  const queryClient = useQueryClient()
  const { success, error } = useToast()
  const [pairModalOpen, setPairModalOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Device | null>(null)
  const [deleting, setDeleting] = useState(false)

  const { data: devices, isLoading, isError } = useQuery({ queryKey: ['devices'], queryFn: devicesApi.list })

  const removeDevice = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await devicesApi.remove(deleteTarget.id)
      success('Device removed')
      queryClient.invalidateQueries({ queryKey: ['devices'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      setDeleteTarget(null)
    } catch (err) {
      error(getErrorMessage(err, 'Could not remove device'))
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Devices"
        description="Android devices that will send your campaigns — pairing arrives in Phase 2."
        actions={
          <Button onClick={() => setPairModalOpen(true)}>
            <Plus className="h-4 w-4" /> Connect Android Device
          </Button>
        }
      />

      <Card className="mb-6">
        <CardBody>
          <Alert tone="info">
            <strong>How sending will work:</strong> in Phase 2 you install the MessageFlow companion app on an Android
            phone, pair it with this account, and campaigns are delivered through the phone's SIM using legitimate
            Android SMS APIs. This page only shows real device registrations — nothing is simulated.
          </Alert>
        </CardBody>
      </Card>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {[1, 2].map((i) => (
            <div key={i} className="h-40 animate-pulse rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900" />
          ))}
        </div>
      ) : isError ? (
        <EmptyState title="Could not load devices" description="Check that the backend is running and try again." />
      ) : !devices || devices.length === 0 ? (
        <div className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
          <EmptyState
            icon={Smartphone}
            title="No Android device connected"
            description="Connect an Android phone to start sending messages."
            action={
              <Button onClick={() => setPairModalOpen(true)}>
                <Plus className="h-4 w-4" /> Connect Android Device
              </Button>
            }
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {devices.map((device) => (
            <Card key={device.id} className="p-5">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
                    <Smartphone className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{device.device_name}</h3>
                    <p className="text-xs text-zinc-400 capitalize">{device.platform}</p>
                  </div>
                </div>
                <button
                  onClick={() => setDeleteTarget(device)}
                  className="rounded-lg p-1.5 text-zinc-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10"
                  aria-label={`Remove ${device.device_name}`}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              <div className="mt-4 flex items-center justify-between border-t border-zinc-100 pt-3 dark:border-zinc-800">
                <StatusBadge status={device.connection_status} />
                <p className="text-xs text-zinc-400">
                  Last seen {device.last_seen ? timeAgo(device.last_seen) : 'never'}
                </p>
              </div>
              <p className="mt-2 text-[11px] text-zinc-400">Registered {formatDateTime(device.created_at)}</p>
            </Card>
          ))}
        </div>
      )}

      {/* Pairing modal — honest about Phase 2 */}
      <Modal
        open={pairModalOpen}
        onClose={() => setPairModalOpen(false)}
        title="Connect an Android device"
        description="Android device pairing is coming in the next phase"
        size="md"
        footer={
          <Button onClick={() => setPairModalOpen(false)}>Got it</Button>
        }
      >
        <div className="space-y-4">
          <div className="flex items-start gap-3 rounded-lg border border-zinc-200 bg-zinc-50/70 p-4 dark:border-zinc-700 dark:bg-zinc-800/40">
            <Info className="mt-0.5 h-4.5 w-4.5 shrink-0 text-brand-600 dark:text-brand-400" />
            <p className="text-sm text-zinc-700 dark:text-zinc-200">
              Android device pairing will be available in the next phase.
            </p>
          </div>
          <p className="text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
            In Phase 2, you'll install the MessageFlow companion app on your Android phone, sign in with this account,
            and approve the connection. The app uses Android's official SMS APIs with the permissions you grant — no
            bypasses, no hidden sending.
          </p>
          <p className="text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
            Until then, campaigns stay in <strong>READY</strong> status and nothing is sent.
          </p>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={removeDevice}
        loading={deleting}
        title="Remove device"
        message={<>Remove <strong>{deleteTarget?.device_name}</strong> from your account? It can be re-registered later.</>}
      />
    </div>
  )
}
