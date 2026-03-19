import { Routes, Route } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { FeedListPage } from './pages/FeedListPage'
import { FeedNewPage } from './pages/FeedNewPage'
import { FeedDetailPage } from './pages/FeedDetailPage'
import { NotFoundPage } from './pages/NotFoundPage'

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<FeedListPage />} />
        <Route path="/feeds/new" element={<FeedNewPage />} />
        <Route path="/feeds/:id" element={<FeedDetailPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AppShell>
  )
}
