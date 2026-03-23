import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { FeedListPage } from './pages/FeedListPage'
import { FeedNewPage } from './pages/FeedNewPage'
import { FeedDetailPage } from './pages/FeedDetailPage'
import { SettingsPage } from './pages/SettingsPage'
import { BackupPage } from './pages/BackupPage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { useAuth } from './context/AuthContext'
import { Spinner } from './components/ui/Spinner'

function ProtectedRoutes() {
  const { username, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner />
      </div>
    )
  }

  if (!username) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<FeedListPage />} />
        <Route path="/feeds/new" element={<FeedNewPage />} />
        <Route path="/feeds/:id" element={<FeedDetailPage />} />
        <Route path="/backup" element={<BackupPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AppShell>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/*" element={<ProtectedRoutes />} />
    </Routes>
  )
}
