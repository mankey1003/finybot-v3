import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { useAuth } from './hooks/useAuth'
import { Cards } from './pages/Cards'
import { ConnectGmail } from './pages/ConnectGmail'
import { Dashboard } from './pages/Dashboard'
import { Insights } from './pages/Insights'
import { Login } from './pages/Login'
import { Chat } from './pages/Chat'
import { Transactions } from './pages/Transactions'

/** Redirect to the right place based on auth state. */
function AuthGuard({ children }: { children: React.ReactNode }) {
  const { state } = useAuth()

  if (state.status === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="h-8 w-8 rounded-full border-4 border-brand-200 border-t-brand-600 animate-spin" />
      </div>
    )
  }

  if (state.status === 'unauthenticated') return <Navigate to="/login" replace />
  if (state.status === 'authenticated_no_gmail') return <Navigate to="/connect-gmail" replace />
  return <>{children}</>
}

export function AppRouter() {
  const { state } = useAuth()

  return (
    <Routes>
      {/* Public */}
      <Route
        path="/login"
        element={
          state.status === 'ready'
            ? <Navigate to="/dashboard" replace />
            : state.status === 'authenticated_no_gmail'
              ? <Navigate to="/connect-gmail" replace />
              : <Login />
        }
      />
      <Route path="/connect-gmail" element={<ConnectGmail />} />

      {/* Protected — requires Firebase auth + Gmail connected */}
      <Route
        element={
          <AuthGuard>
            <Layout />
          </AuthGuard>
        }
      >
        <Route path="/dashboard"    element={<Dashboard />} />
        <Route path="/transactions" element={<Transactions />} />
        <Route path="/chat"         element={<Chat />} />
        <Route path="/insights"     element={<Insights />} />
        <Route path="/cards"        element={<Cards />} />
      </Route>

      {/* Default redirect */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
