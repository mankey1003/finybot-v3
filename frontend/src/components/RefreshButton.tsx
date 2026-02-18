import { RefreshCw } from 'lucide-react'

interface Props {
  onRefresh: () => void
  isRunning: boolean
  lastSyncAt?: string | null
}

export function RefreshButton({ onRefresh, isRunning, lastSyncAt }: Props) {
  return (
    <div className="flex items-center gap-3">
      {lastSyncAt && (
        <span className="text-xs text-gray-400 hidden sm:block">
          Last synced {new Date(lastSyncAt).toLocaleDateString()}
        </span>
      )}
      <button
        onClick={onRefresh}
        disabled={isRunning}
        className="flex items-center gap-2 rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-medium text-white
                   hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        <RefreshCw className={`h-3.5 w-3.5 ${isRunning ? 'animate-spin' : ''}`} />
        {isRunning ? 'Syncing…' : 'Refresh'}
      </button>
    </div>
  )
}
