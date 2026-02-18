import { CreditCard, LayoutDashboard, LogOut, Sparkles, List } from 'lucide-react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useSyncJob } from '../hooks/useSyncJob'
import { RefreshButton } from './RefreshButton'
import { SyncStatusBanner } from './SyncStatusBanner'

const NAV = [
  { to: '/dashboard',    label: 'Dashboard',     Icon: LayoutDashboard },
  { to: '/transactions', label: 'Transactions',   Icon: List },
  { to: '/insights',     label: 'Insights',       Icon: Sparkles },
  { to: '/cards',        label: 'Cards',          Icon: CreditCard },
]

export function Layout() {
  const { state, signOut } = useAuth()
  const navigate = useNavigate()
  const user = state.status === 'ready' ? state.user : null

  const { syncState, triggerSync, dismissSync, isRunning } = useSyncJob()

  const handleSignOut = async () => {
    await signOut()
    navigate('/login')
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* ── Sidebar ─────────────────────────────────── */}
      <aside className="w-56 shrink-0 flex flex-col bg-white border-r border-gray-200">
        <div className="px-5 py-5 border-b border-gray-100">
          <span className="text-lg font-bold text-brand-600">FinyBot</span>
          <p className="text-xs text-gray-400 mt-0.5">Credit card tracker</p>
        </div>

        <nav className="flex-1 py-4 space-y-0.5 px-2">
          {NAV.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors
                 ${isActive
                   ? 'bg-brand-50 text-brand-700'
                   : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'}`
              }
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="px-4 py-4 border-t border-gray-100">
          {user && (
            <div className="mb-3">
              <p className="text-xs font-medium text-gray-700 truncate">{user.displayName}</p>
              <p className="text-xs text-gray-400 truncate">{user.email}</p>
            </div>
          )}
          <button
            onClick={handleSignOut}
            className="flex items-center gap-2 text-xs text-gray-500 hover:text-gray-700 transition-colors"
          >
            <LogOut className="h-3.5 w-3.5" />
            Sign out
          </button>
        </div>
      </aside>

      {/* ── Main content ────────────────────────────── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex items-center justify-between px-6 py-4 bg-white border-b border-gray-200">
          <div /> {/* spacer — page title is rendered by each page */}
          <RefreshButton
            onRefresh={triggerSync}
            isRunning={isRunning}
          />
        </header>

        {/* Sync status banner */}
        {syncState.status !== 'idle' && (
          <div className="px-6 pt-4">
            <SyncStatusBanner
              status={syncState.status}
              results={syncState.results}
              errorReason={syncState.errorReason}
              onDismiss={dismissSync}
            />
          </div>
        )}

        {/* Page content */}
        <main className="flex-1 overflow-y-auto px-6 py-6">
          <Outlet context={{ triggerSync, syncState }} />
        </main>
      </div>
    </div>
  )
}
