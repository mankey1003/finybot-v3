import { format } from 'date-fns'
import { AlertCircle, Loader2, Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../lib/api'

interface SpendMonth {
  total: number
  by_card: Record<string, number>
  by_category: Record<string, number>
  transaction_count: number
}

interface InsightsResponse {
  months: string[]
  spend_data: Record<string, SpendMonth>
  narrative: string
}

interface Statement { billing_month: string }

function fmt(val: number) {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val)
}

const BAR_COLORS = ['bg-brand-500', 'bg-purple-400', 'bg-amber-400', 'bg-green-400', 'bg-rose-400', 'bg-teal-400']

export function Insights() {
  const [availableMonths, setAvailableMonths] = useState<string[]>([])
  const [selectedMonths, setSelectedMonths] = useState<string[]>([])
  const [result, setResult] = useState<InsightsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api<Statement[]>('/api/statements').then(stmts => {
      const unique = [...new Set(stmts.map(s => s.billing_month))].sort().reverse()
      setAvailableMonths(unique)
      // Default: select last 3 months
      setSelectedMonths(unique.slice(0, 3))
    }).catch(() => {})
  }, [])

  const toggleMonth = (m: string) => {
    setSelectedMonths(prev =>
      prev.includes(m) ? prev.filter(x => x !== m) : [...prev, m].slice(0, 6)
    )
  }

  const generate = async () => {
    if (selectedMonths.length < 1) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const sorted = [...selectedMonths].sort().reverse()
      const data = await api<InsightsResponse>(`/api/insights?months=${sorted.join(',')}`)
      setResult(data)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to generate insights')
    } finally {
      setLoading(false)
    }
  }

  // Bar chart: max total across months as 100%
  const maxTotal = result
    ? Math.max(...Object.values(result.spend_data).map(d => d.total), 1)
    : 1

  return (
    <div className="max-w-3xl">
      <div className="flex items-baseline gap-3 mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Insights</h1>
        <Sparkles className="h-5 w-5 text-brand-500" />
      </div>

      {availableMonths.length === 0 && (
        <p className="text-sm text-gray-400">Sync your statements first to generate insights.</p>
      )}

      {availableMonths.length > 0 && (
        <>
          {/* Month selector */}
          <div className="bg-white rounded-xl border border-gray-200 px-5 py-4 mb-4">
            <p className="text-sm font-medium text-gray-700 mb-3">Select months to compare (up to 6)</p>
            <div className="flex flex-wrap gap-2">
              {availableMonths.map((m, i) => (
                <button
                  key={m}
                  onClick={() => toggleMonth(m)}
                  className={`rounded-lg px-3 py-1.5 text-xs font-medium border transition-colors
                    ${selectedMonths.includes(m)
                      ? 'bg-brand-600 text-white border-brand-600'
                      : 'bg-white text-gray-600 border-gray-300 hover:border-brand-400'}`}
                >
                  {format(new Date(m + '-01'), 'MMM yyyy')}
                </button>
              ))}
            </div>

            <button
              onClick={generate}
              disabled={loading || selectedMonths.length === 0}
              className="mt-4 flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2 text-sm font-semibold text-white
                         hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              {loading ? 'Generating…' : 'Generate Insights'}
            </button>
          </div>

          {error && (
            <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 rounded-lg px-4 py-3 mb-4">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}

          {result && (
            <div className="space-y-4">
              {/* Spend bar chart */}
              <div className="bg-white rounded-xl border border-gray-200 px-5 py-5">
                <h3 className="text-sm font-semibold text-gray-700 mb-4">Monthly total spend</h3>
                <div className="space-y-3">
                  {[...result.months].sort().reverse().map((m, i) => {
                    const d = result.spend_data[m]
                    const pct = Math.round((d.total / maxTotal) * 100)
                    return (
                      <div key={m}>
                        <div className="flex justify-between text-xs text-gray-500 mb-1">
                          <span>{format(new Date(m + '-01'), 'MMM yyyy')}</span>
                          <span className="font-medium text-gray-800">{fmt(d.total)}</span>
                        </div>
                        <div className="h-6 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${BAR_COLORS[i % BAR_COLORS.length]} transition-all`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Category breakdown — latest month */}
              {result.months.length > 0 && (() => {
                const latestMonth = [...result.months].sort().reverse()[0]
                const categories = result.spend_data[latestMonth]?.by_category ?? {}
                const sorted = Object.entries(categories).sort((a, b) => b[1] - a[1])
                const catMax = sorted[0]?.[1] ?? 1
                return (
                  <div className="bg-white rounded-xl border border-gray-200 px-5 py-5">
                    <h3 className="text-sm font-semibold text-gray-700 mb-4">
                      {format(new Date(latestMonth + '-01'), 'MMMM yyyy')} — by category
                    </h3>
                    <div className="space-y-2.5">
                      {sorted.map(([cat, amt], i) => (
                        <div key={cat}>
                          <div className="flex justify-between text-xs text-gray-500 mb-0.5">
                            <span>{cat}</span>
                            <span className="text-gray-800">{fmt(amt)}</span>
                          </div>
                          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${BAR_COLORS[i % BAR_COLORS.length]}`}
                              style={{ width: `${Math.round((amt / catMax) * 100)}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })()}

              {/* Gemini narrative */}
              <div className="bg-gradient-to-br from-brand-50 to-white rounded-xl border border-brand-100 px-5 py-5">
                <div className="flex items-center gap-2 mb-3">
                  <Sparkles className="h-4 w-4 text-brand-600" />
                  <h3 className="text-sm font-semibold text-brand-700">AI Analysis</h3>
                </div>
                <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">
                  {result.narrative}
                </p>
                <p className="text-xs text-gray-400 mt-3">Powered by Gemini 3 Flash</p>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
