import { useQueryClient } from '@tanstack/react-query'
import { KeyRound, UserRound } from 'lucide-react'
import { useState } from 'react'
import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { Field, Input } from '../components/ui/Form'
import { PageHeader, Alert } from '../components/ui/Misc'
import { useToast } from '../components/ui/Toast'
import { getErrorMessage } from '../lib/api'
import { useAuth } from '../hooks/useAuth'
import { authApi } from '../services/api'

export function SettingsPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const { success, error } = useToast()

  const [name, setName] = useState(user?.name ?? '')
  const [savingProfile, setSavingProfile] = useState(false)

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [savingPassword, setSavingPassword] = useState(false)

  const saveProfile = async (event: React.FormEvent) => {
    event.preventDefault()
    setSavingProfile(true)
    try {
      const updated = await authApi.updateProfile(name.trim())
      queryClient.setQueryData(['me'], updated)
      success('Profile updated')
    } catch (err) {
      error(getErrorMessage(err, 'Could not update profile'))
    } finally {
      setSavingProfile(false)
    }
  }

  const changePassword = async (event: React.FormEvent) => {
    event.preventDefault()
    if (newPassword !== confirmPassword) {
      error('New passwords do not match')
      return
    }
    setSavingPassword(true)
    try {
      await authApi.changePassword(currentPassword, newPassword)
      success('Password changed')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err) {
      error(getErrorMessage(err, 'Could not change password'))
    } finally {
      setSavingPassword(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl animate-fade-in">
      <PageHeader title="Settings" description="Manage your account profile and security." />

      <Card className="mb-6">
        <CardHeader title="Profile" description="Your name and account email" />
        <CardBody>
          <form onSubmit={saveProfile} className="space-y-4">
            <Field label="Name">
              <Input value={name} onChange={(event) => setName(event.target.value)} minLength={2} required />
            </Field>
            <Field label="Email" hint="Email cannot be changed in Phase 1.">
              <Input value={user?.email ?? ''} disabled />
            </Field>
            <div className="flex justify-end">
              <Button type="submit" loading={savingProfile}>
                <UserRound className="h-4 w-4" /> Save profile
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>

      <Card className="mb-6">
        <CardHeader title="Change password" description="Use at least 8 characters with letters and numbers" />
        <CardBody>
          <form onSubmit={changePassword} className="space-y-4">
            <Field label="Current password" required>
              <Input
                type="password"
                autoComplete="current-password"
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
                required
              />
            </Field>
            <Field label="New password" required>
              <Input
                type="password"
                autoComplete="new-password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                minLength={8}
                required
              />
            </Field>
            <Field label="Confirm new password" required>
              <Input
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                minLength={8}
                required
              />
            </Field>
            <div className="flex justify-end">
              <Button type="submit" variant="outline" loading={savingPassword}>
                <KeyRound className="h-4 w-4" /> Update password
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="About MessageFlow" />
        <CardBody className="space-y-3 text-sm text-zinc-500 dark:text-zinc-400">
          <Alert tone="info">
            <strong>Phase 1:</strong> import contacts, build groups and templates, prepare and validate campaigns,
            maintain opt-outs. No SMS is sent until an Android device is connected in Phase 2.
          </Alert>
          <p>
            Your data is scoped to your account only — other users can never see your contacts, campaigns, or logs.
          </p>
        </CardBody>
      </Card>
    </div>
  )
}
