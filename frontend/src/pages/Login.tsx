import { CreditCard } from 'lucide-react'
import { useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { logFrontendError } from '../lib/api'

export function Login() {
  const { signIn } = useAuth()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSignIn = async () => {
    setLoading(true)
    setError(null)
    try {
      await signIn()
      // useAuth will update state → router redirects automatically
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Sign-in failed'
      setError(msg)
      logFrontendError(msg, err instanceof Error ? err.stack : undefined)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-brand-50 to-white">
      <div className="w-full max-w-sm px-8 py-10 bg-white rounded-2xl shadow-lg text-center">
        <div className="flex justify-center mb-4">
          <div className="p-3 rounded-full bg-brand-50">
            <CreditCard className="h-8 w-8 text-brand-600" />
          </div>
        </div>

        <h1 className="text-2xl font-bold text-gray-900">FinyBot</h1>
        <p className="mt-2 text-sm text-gray-500">
          Your monthly credit card expense tracker
        </p>

        <ul className="mt-6 space-y-2 text-left text-sm text-gray-600">
          {[
            'Fetches statements from your Gmail',
            'Extracts transactions with AI',
            'Tracks spend across all your cards',
          ].map(item => (
            <li key={item} className="flex items-start gap-2">
              <span className="text-brand-500 mt-0.5">✓</span>
              {item}
            </li>
          ))}
        </ul>

        {error && (
          <p className="mt-4 text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
        )}

        <button
          onClick={handleSignIn}
          disabled={loading}
          className="mt-6 w-full flex items-center justify-center gap-3 rounded-xl border border-gray-300
                     bg-white px-4 py-3 text-sm font-medium text-gray-700 shadow-sm
                     hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {/* Google logo SVG */}
          <svg className="h-5 w-5" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"/>
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
          </svg>
          {loading ? 'Signing in…' : 'Sign in with Google'}
        </button>

        <p className="mt-4 text-xs text-gray-400">
          We only read your emails to find credit card statements.
        </p>
      </div>
    </div>
  )
}
