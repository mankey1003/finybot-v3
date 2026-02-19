import { format } from 'date-fns'
import { AlertCircle, Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useInfiniteTransactions } from '../hooks/useInfiniteTransactions'
import { api } from '../lib/api'

interface CardProvider { id: string; name: string }

const CATEGORY_COLORS: Record<string, string> = {
  Food:          'bg-orange-100 text-orange-700',
  Travel:        'bg-blue-100 text-blue-700',
  Shopping:      'bg-pink-100 text-pink-700',
  Entertainment: 'bg-purple-100 text-purple-700',
  Utilities:     'bg-gray-100 text-gray-600',
  Healthcare:    'bg-green-100 text-green-700',
  Fuel:          'bg-yellow-100 text-yellow-700',
  EMI:           'bg-red-100 text-red-700',
  Other:         'bg-gray-100 text-gray-500',
}

function fmt(val: number, currency: string) {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency }).format(val)
}

export function Transactions() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [cards, setCards] = useState<CardProvider[]>([])

  const billingMonth  = searchParams.get('billing_month') ?? ''
  const cardProvider  = searchParams.get('card_provider') ?? ''

  const { transactions, loading, error, hasMore, sentinelRef } =
    useInfiniteTransactions({
      billing_month: billingMonth || undefined,
      card_provider: cardProvider || undefined,
    })

  useEffect(() => {
    api<CardProvider[]>('/api/cards').then(setCards).catch(() => {})
  }, [])

  const setFilter = (key: string, val: string) => {
    const next = new URLSearchParams(searchParams)
    val ? next.set(key, val) : next.delete(key)
    setSearchParams(next)
  }

  // Build unique billing months from cards for the month filter
  const [months, setMonths] = useState<string[]>([])
  useEffect(() => {
    api<{ id: string; billing_month: string }[]>('/api/statements')
      .then(stmts => {
        const unique = [...new Set(stmts.map(s => (s as any).billing_month))].sort().reverse()
        setMonths(unique as string[])
      })
      .catch(() => {})
  }, [])

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Transactions</h1>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-6">
        <select
          value={billingMonth}
          onChange={e => setFilter('billing_month', e.target.value)}
          className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          <option value="">All months</option>
          {months.map(m => (
            <option key={m} value={m}>
              {format(new Date(m + '-01'), 'MMMM yyyy')}
            </option>
          ))}
        </select>

        <select
          value={cardProvider}
          onChange={e => setFilter('card_provider', e.target.value)}
          className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          <option value="">All cards</option>
          {cards.map(c => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>

        {(billingMonth || cardProvider) && (
          <button
            onClick={() => setSearchParams({})}
            className="text-sm text-gray-400 hover:text-gray-600"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Error state */}
      {error && (
        <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 rounded-lg px-4 py-3 mb-4">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Transaction list */}
      {transactions.length === 0 && !loading && (
        <p className="text-center text-gray-400 py-16 text-sm">
          No transactions found. Try a different filter or sync your statements.
        </p>
      )}

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="divide-y divide-gray-100">
          {transactions.map(tx => (
            <div key={tx.id} className="flex items-center gap-4 px-5 py-3.5">
              <div className="w-16 shrink-0 text-right">
                <p className="text-xs font-medium text-gray-500">
                  {format(new Date(tx.date), 'dd MMM')}
                </p>
                <p className="text-xs text-gray-400">
                  {format(new Date(tx.date), 'yyyy')}
                </p>
              </div>

              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">{tx.description}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-medium
                      ${CATEGORY_COLORS[tx.category] ?? CATEGORY_COLORS.Other}`}
                  >
                    {tx.category}
                  </span>
                  <span className="text-xs text-gray-400 capitalize">{tx.card_provider}</span>
                </div>
              </div>

              <div className="text-right shrink-0">
                <p className={`text-sm font-semibold ${tx.debit_or_credit === 'credit' ? 'text-green-600' : 'text-gray-900'}`}>
                  {tx.debit_or_credit === 'credit' ? '+' : ''}
                  {fmt(tx.amount, tx.currency)}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Infinite scroll sentinel + loading indicator */}
      <div ref={sentinelRef} className="py-6 flex justify-center">
        {loading && <Loader2 className="h-5 w-5 animate-spin text-gray-400" />}
        {!hasMore && transactions.length > 0 && (
          <p className="text-xs text-gray-400">All transactions loaded</p>
        )}
      </div>
    </div>
  )
}
