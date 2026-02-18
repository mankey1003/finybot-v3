import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../lib/api'

type JobStatus = 'idle' | 'pending' | 'processing' | 'done' | 'failed'

interface JobResult {
  processed: number
  skipped: number
  failed: number
  errors: string[]
}

interface SyncState {
  status: JobStatus
  results: JobResult | null
  errorReason: string | null
}

const POLL_INTERVAL_MS = 3000

/**
 * Manages the full sync lifecycle: trigger → poll → done/failed.
 * The "Refresh" button calls triggerSync(); the hook handles polling internally.
 * onComplete is called when status reaches "done".
 */
export function useSyncJob(onComplete?: () => void) {
  const [syncState, setSyncState] = useState<SyncState>({
    status: 'idle',
    results: null,
    errorReason: null,
  })
  const jobIdRef = useRef<string | null>(null)
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current)
      pollTimerRef.current = null
    }
  }, [])

  const pollStatus = useCallback(async (jobId: string) => {
    try {
      const job = await api<{
        job_id: string
        status: string
        results: JobResult | null
        error_reason: string | null
      }>(`/api/sync/status/${jobId}`)

      if (job.status === 'done') {
        stopPolling()
        setSyncState({ status: 'done', results: job.results, errorReason: null })
        onComplete?.()
      } else if (job.status === 'failed') {
        stopPolling()
        setSyncState({ status: 'failed', results: job.results, errorReason: job.error_reason })
      } else {
        setSyncState(prev => ({ ...prev, status: job.status as JobStatus }))
      }
    } catch (err) {
      // Network hiccup during polling — keep polling, don't fail the job
      console.warn('Sync poll failed (will retry):', err)
    }
  }, [onComplete, stopPolling])

  const triggerSync = useCallback(async () => {
    setSyncState({ status: 'pending', results: null, errorReason: null })
    try {
      const { job_id } = await api<{ job_id: string; message: string }>('/api/sync', {
        method: 'POST',
      })
      jobIdRef.current = job_id
      // Start polling
      pollTimerRef.current = setInterval(() => pollStatus(job_id), POLL_INTERVAL_MS)
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Failed to start sync'
      setSyncState({ status: 'failed', results: null, errorReason: msg })
    }
  }, [pollStatus])

  const dismissSync = useCallback(() => {
    stopPolling()
    setSyncState({ status: 'idle', results: null, errorReason: null })
  }, [stopPolling])

  // Clean up on unmount
  useEffect(() => () => stopPolling(), [stopPolling])

  const isRunning = syncState.status === 'pending' || syncState.status === 'processing'

  return { syncState, triggerSync, dismissSync, isRunning }
}
