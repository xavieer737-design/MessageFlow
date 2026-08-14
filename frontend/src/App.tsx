import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './components/layout/AppLayout'
import { useAuth } from './hooks/useAuth'
import { Spinner } from './components/ui/Misc'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { DashboardPage } from './pages/DashboardPage'
import { ContactsPage } from './pages/ContactsPage'
import { GroupsPage } from './pages/GroupsPage'
import { CampaignsPage } from './pages/CampaignsPage'
import { CampaignWizardPage } from './pages/CampaignWizardPage'
import { CampaignDetailPage } from './pages/CampaignDetailPage'
import { TemplatesPage } from './pages/TemplatesPage'
import { DevicesPage } from './pages/DevicesPage'
import { MessageLogsPage } from './pages/MessageLogsPage'
import { OptOutsPage } from './pages/OptOutsPage'
import { SettingsPage } from './pages/SettingsPage'
import { NotFoundPage } from './pages/NotFoundPage'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading, isError } = useAuth()
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950">
        <Spinner className="h-7 w-7" />
      </div>
    )
  }
  if (isError || !user) return <Navigate to="/login" replace />
  return <>{children}</>
}

function GuestRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth()
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950">
        <Spinner className="h-7 w-7" />
      </div>
    )
  }
  if (user) return <Navigate to="/" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<GuestRoute><LoginPage /></GuestRoute>} />
      <Route path="/register" element={<GuestRoute><RegisterPage /></GuestRoute>} />
      <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/contacts" element={<ContactsPage />} />
        <Route path="/groups" element={<GroupsPage />} />
        <Route path="/campaigns" element={<CampaignsPage />} />
        <Route path="/campaigns/new" element={<CampaignWizardPage />} />
        <Route path="/campaigns/:id" element={<CampaignDetailPage />} />
        <Route path="/campaigns/:id/edit" element={<CampaignWizardPage />} />
        <Route path="/templates" element={<TemplatesPage />} />
        <Route path="/devices" element={<DevicesPage />} />
        <Route path="/messages" element={<MessageLogsPage />} />
        <Route path="/optouts" element={<OptOutsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
