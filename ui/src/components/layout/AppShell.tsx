import { Link, useLocation } from 'react-router-dom'
import { Rss, LayoutDashboard, PlusCircle, Settings, LogOut, HardDriveDownload } from 'lucide-react'
import { cn } from '../../lib/cn'
import { useAuth } from '../../context/AuthContext'

const nav = [
  { label: 'Feeds', to: '/', icon: LayoutDashboard },
  { label: 'New Feed', to: '/feeds/new', icon: PlusCircle },
  { label: 'Backup & Restore', to: '/backup', icon: HardDriveDownload },
  { label: 'Settings', to: '/settings', icon: Settings },
]

export function AppShell({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation()
  const { username, logout } = useAuth()

  return (
    <div className="flex min-h-screen bg-gray-50">
      <aside className="flex w-56 flex-col border-r border-gray-200 bg-white">
        <div className="flex h-14 items-center gap-2 border-b border-gray-200 px-4">
          <Rss className="h-5 w-5 text-orange-500" />
          <span className="font-semibold text-gray-800">RSS Generator</span>
        </div>
        <nav className="flex-1 p-3">
          {nav.map(({ label, to, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className={cn(
                'flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                pathname === to
                  ? 'bg-orange-50 text-orange-600'
                  : 'text-gray-600 hover:bg-gray-100 hover:text-gray-800',
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          ))}
        </nav>
        <div className="border-t border-gray-200 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="truncate text-xs font-medium text-gray-600">{username}</span>
            <button
              onClick={logout}
              title="Sign out"
              className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
            >
              <LogOut className="h-3.5 w-3.5" />
            </button>
          </div>
          <p className="text-xs text-gray-400">v0.1.0</p>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  )
}
