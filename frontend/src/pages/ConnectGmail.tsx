import { Mail, ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { api, ApiError, logFrontendError } from '../lib/api'

export function ConnectGmail() {
  const [searchParams] = useSearchParams()
  const { refreshGmailStatus } = useAuth()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Handle error params from backend OAuth callback redirect
  useEffect(() => {
    const backendError = searchParams.get('error')
    const errorMessages: Record<string, string> = {
      session_expired: 'The authorization session expired. Please try again.',
      invalid_state: 'Invalid authorization state. Please try again.',
      token_exchange_failed: 'Failed to exchange authorization code. Please try again.',
      no_refresh_token: 'Google did not return a refresh token. Please try again and ensure you grant all permissions.',
      storage_failed: 'Failed to save your authorization. Please try again.',
    }
    if (backendError) {
      setError(errorMessages[backendError] ?? `Authorization failed: ${backendError}`)
    }
  }, [searchParams])

  const handleConnect = async () => {
    setLoading(true)
    setError(null)
    try {
      // Flow 2 — Step 1: get the Google consent URL from the backend
      const { auth_url } = await api<{ auth_url: string }>('/api/auth/gmail/initiate')
      // Redirect the browser to Google's consent screen
      window.location.href = auth_url
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Failed to start Gmail authorization'
      setError(msg)
      logFrontendError(msg, err instanceof Error ? err.stack : undefined)
      setLoading(false)
    }
  }

  // After backend redirects back with ?gmail_connected=1, refresh status and go to dashboard
  useEffect(() => {
    if (searchParams.get('gmail_connected') === '1') {
      refreshGmailStatus()
      navigate('/dashboard', { replace: true })
    }
  }, [searchParams, refreshGmailStatus, navigate])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-brand-50 to-white">
      <div className="w-full max-w-sm px-8 py-10 bg-white rounded-2xl shadow-lg text-center">
        <div className="flex justify-center mb-4">
          <div className="p-3 rounded-full bg-blue-50">
            <Mail className="h-8 w-8 text-blue-600" />
          </div>
        </div>

        <h2 className="text-xl font-bold text-gray-900">Connect your Gmail</h2>
        <p className="mt-2 text-sm text-gray-500">
          FinyBot needs read-only access to your Gmail to find credit card statement PDFs.
        </p>

        <div className="mt-6 space-y-3 text-left">
          {[
            { icon: ShieldCheck, text: 'Read-only access — we never send, delete, or modify emails' },
            { icon: ShieldCheck, text: 'Only fetches PDFs matching your card provider settings' },
            { icon: ShieldCheck, text: 'Syncs once a month, or whenever you click Refresh' },
          ].map(({ icon: Icon, text }) => (
            <div key={text} className="flex items-start gap-2 text-sm text-gray-600">
              <Icon className="h-4 w-4 text-green-500 shrink-0 mt-0.5" />
              {text}
            </div>
          ))}
        </div>

        {error && (
          <p className="mt-4 text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2 text-left">{error}</p>
        )}

        <button
          onClick={handleConnect}
          disabled={loading}
          className="mt-6 w-full rounded-xl bg-brand-600 px-4 py-3 text-sm font-semibold text-white
                     hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? 'Redirecting to Google…' : 'Connect Gmail'}
        </button>

        <p className="mt-3 text-xs text-gray-400">
          This is a one-time step. You won't need to do this again.
        </p>
      </div>
    </div>
  )
}
