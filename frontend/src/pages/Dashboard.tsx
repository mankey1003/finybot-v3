import { format } from 'date-fns'
import { AlertCircle, CreditCard, Inbox } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { api } from '../lib/api'

interface Statement {
  id: string
  card_provider: string
  billing_month: string
  statement_date: string | null
  due_date: string | null
  total_amount_due: number
  min_payment_due: number
  currency: string
  status: string
  error_reason: string | null
}

interface MonthGroup {
  month: string
  statements: Statement[]
  total: number
}

interface OutletCtx {
  triggerSync: () => void
  syncState: { status: string }
}

function fmt(val: number, currency: string) {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency }).format(val)
}

export function Dashboard() {
  const { state } = useAuth()
  const { triggerSync, syncState } = useOutletContext<OutletCtx>()
  const [statements, setStatements] = useState<Statement[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const user = state.status === 'ready' ? state.user : null

  const fetchStatements = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api<Statement[]>('/api/statements')
      setStatements(data)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load statements')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchStatements() }, [])

  // Reload data when sync completes
  useEffect(() => {
    if (syncState.status === 'done') fetchStatements()
  }, [syncState.status])

  // Group statements by billing month
  const grouped: MonthGroup[] = []
  const seen = new Set<string>()
  for (const s of statements) {
    if (!seen.has(s.billing_month)) {
      seen.add(s.billing_month)
      const monthStmts = statements.filter(x => x.billing_month === s.billing_month)
      grouped.push({
        month: s.billing_month,
        statements: monthStmts,
        total: monthStmts
          .filter(x => x.status === 'processed')
          .reduce((sum, x) => sum + x.total_amount_due, 0),
      })
    }
  }

  const noData = !loading && statements.length === 0

  return (
    <div className="max-w-3xl">
      <div className="flex items-baseline justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {user ? `Hello, ${user.displayName?.split(' ')[0]}` : 'Dashboard'}
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">Monthly credit card overview</p>
        </div>
      </div>

      {/* First-time empty state */}
      {noData && (
        <div className="rounded-2xl border-2 border-dashed border-gray-200 p-12 text-center">
          <Inbox className="h-10 w-10 text-gray-300 mx-auto mb-4" />
          <h3 className="text-base font-semibold text-gray-700">No statements yet</h3>
          <p className="text-sm text-gray-400 mt-1 mb-5">
            Click <strong>Refresh</strong> to fetch your credit card statements from Gmail.
          </p>
          <button
            onClick={triggerSync}
            disabled={syncState.status !== 'idle'}
            className="rounded-xl bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white
                       hover:bg-brand-700 disabled:opacity-50 transition-colors"
          >
            Sync Now
          </button>
        </div>
      )}

      {loading && (
        <div className="space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-24 rounded-xl bg-gray-100 animate-pulse" />
          ))}
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 rounded-lg px-4 py-3">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Month groups */}
      <div className="space-y-6">
        {grouped.map(group => (
          <div key={group.month} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            {/* Month header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 bg-gray-50">
              <h2 className="font-semibold text-gray-800">
                {format(new Date(group.month + '-01'), 'MMMM yyyy')}
              </h2>
              <span className="text-lg font-bold text-gray-900">
                {fmt(group.total, group.statements[0]?.currency || 'INR')}
              </span>
            </div>

            {/* Cards for this month */}
            <div className="divide-y divide-gray-100">
              {group.statements.map(s => (
                <div key={s.id} className="flex items-center gap-4 px-5 py-4">
                  <div className="p-2 rounded-lg bg-brand-50">
                    <CreditCard className="h-5 w-5 text-brand-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 capitalize">{s.card_provider}</p>
                    <div className="flex items-center gap-3 mt-0.5 text-xs text-gray-400">
                      {s.due_date && (
                        <span>Due {format(new Date(s.due_date), 'dd MMM')}</span>
                      )}
                      {s.status !== 'processed' && (
                        <span className="text-amber-600 capitalize">{s.status}</span>
                      )}
                      {s.error_reason && (
                        <span className="text-red-500">{s.error_reason.replace(/_/g, ' ')}</span>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold text-gray-900">
                      {fmt(s.total_amount_due, s.currency)}
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      Min {fmt(s.min_payment_due, s.currency)}
                    </p>
                  </div>
                </div>
              ))}
            </div>

            <div className="px-5 py-3 border-t border-gray-100">
              <Link
                to={`/transactions?billing_month=${group.month}`}
                className="text-xs text-brand-600 hover:text-brand-700 font-medium"
              >
                View transactions →
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
