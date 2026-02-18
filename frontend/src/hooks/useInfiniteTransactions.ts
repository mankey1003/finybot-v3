import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'

export interface Transaction {
  id: string
  card_provider: string
  statement_id: string
  date: string
  billing_month: string
  description: string
  amount: number
  currency: string
  debit_or_credit: string
  category: string
}

interface PageResponse {
  transactions: Transaction[]
  next_cursor: string | null
  has_more: boolean
}

interface UseInfiniteTransactionsOptions {
  billing_month?: string
  card_provider?: string
  limit?: number
}

/**
 * Cursor-based infinite scroll hook for transactions.
 * Uses IntersectionObserver to auto-fetch next pages when sentinel div is visible.
 */
export function useInfiniteTransactions(opts: UseInfiniteTransactionsOptions = {}) {
  const { billing_month, card_provider, limit = 20 } = opts

  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const sentinelRef = useRef<HTMLDivElement | null>(null)
  const isFetchingRef = useRef(false)

  const buildUrl = useCallback(
    (cursorId?: string | null) => {
      const params = new URLSearchParams({ limit: String(limit) })
      if (billing_month) params.set('billing_month', billing_month)
      if (card_provider) params.set('card_provider', card_provider)
      if (cursorId) params.set('cursor', cursorId)
      return `/api/transactions?${params}`
    },
    [billing_month, card_provider, limit]
  )

  const fetchPage = useCallback(
    async (cursorId?: string | null) => {
      if (isFetchingRef.current) return
      isFetchingRef.current = true
      setLoading(true)
      setError(null)

      try {
        const data = await api<PageResponse>(buildUrl(cursorId))
        setTransactions(prev => (cursorId ? [...prev, ...data.transactions] : data.transactions))
        setCursor(data.next_cursor)
        setHasMore(data.has_more)
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Failed to load transactions'
        setError(msg)
      } finally {
        setLoading(false)
        isFetchingRef.current = false
      }
    },
    [buildUrl]
  )

  // Reset and reload when filters change
  useEffect(() => {
    setTransactions([])
    setCursor(null)
    setHasMore(true)
    fetchPage(null)
  }, [billing_month, card_provider]) // eslint-disable-line react-hooks/exhaustive-deps

  // IntersectionObserver — fetches next page when sentinel div enters viewport
  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel) return

    const observer = new IntersectionObserver(
      entries => {
        if (entries[0].isIntersecting && hasMore && !loading) {
          fetchPage(cursor)
        }
      },
      { rootMargin: '200px' }
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [cursor, hasMore, loading, fetchPage])

  const refresh = useCallback(() => {
    setTransactions([])
    setCursor(null)
    setHasMore(true)
    fetchPage(null)
  }, [fetchPage])

  return { transactions, loading, error, hasMore, sentinelRef, refresh }
}
