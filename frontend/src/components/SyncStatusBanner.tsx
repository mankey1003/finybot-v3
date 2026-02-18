import { AlertCircle, CheckCircle, Loader2, X } from 'lucide-react'

type JobStatus = 'idle' | 'pending' | 'processing' | 'done' | 'failed'

interface JobResult {
  processed: number
  skipped: number
  failed: number
  errors: string[]
}

interface Props {
  status: JobStatus
  results: JobResult | null
  errorReason: string | null
  onDismiss: () => void
}

export function SyncStatusBanner({ status, results, errorReason, onDismiss }: Props) {
  if (status === 'idle') return null

  if (status === 'pending' || status === 'processing') {
    return (
      <div className="flex items-center gap-3 rounded-lg bg-brand-50 border border-brand-100 px-4 py-3 text-sm text-brand-700">
        <Loader2 className="h-4 w-4 animate-spin shrink-0" />
        <span>
          {status === 'pending' ? 'Starting sync…' : 'Fetching statements from Gmail…'}
        </span>
      </div>
    )
  }

  if (status === 'done') {
    return (
      <div className="flex items-start gap-3 rounded-lg bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-800">
        <CheckCircle className="h-4 w-4 shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="font-medium">Sync complete</p>
          {results && (
            <p className="text-green-700 mt-0.5">
              {results.processed} statement{results.processed !== 1 ? 's' : ''} processed
              {results.skipped > 0 && `, ${results.skipped} already up-to-date`}
              {results.failed > 0 && `, ${results.failed} failed`}
            </p>
          )}
          {results?.errors?.length ? (
            <ul className="mt-1 list-disc list-inside text-red-600">
              {results.errors.map((e, i) => <li key={i}>{e}</li>)}
            </ul>
          ) : null}
        </div>
        <button onClick={onDismiss} className="text-green-600 hover:text-green-800">
          <X className="h-4 w-4" />
        </button>
      </div>
    )
  }

  // failed
  return (
    <div className="flex items-start gap-3 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-800">
      <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
      <div className="flex-1">
        <p className="font-medium">Sync failed</p>
        {errorReason && <p className="text-red-700 mt-0.5">{errorReason}</p>}
      </div>
      <button onClick={onDismiss} className="text-red-600 hover:text-red-800">
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}
