import { BrowserRouter } from 'react-router-dom'
import { AppRouter } from './router'
import { useEffect } from 'react'
import { logFrontendError } from './lib/api'

// Global error sink — catches unhandled JS errors and reports them to the backend
function useGlobalErrorLogging() {
  useEffect(() => {
    const onError = (event: ErrorEvent) => {
      logFrontendError(event.message, event.error?.stack)
    }
    const onUnhandledRejection = (event: PromiseRejectionEvent) => {
      const msg = event.reason instanceof Error ? event.reason.message : String(event.reason)
      const stack = event.reason instanceof Error ? event.reason.stack : undefined
      logFrontendError(`Unhandled promise rejection: ${msg}`, stack)
    }

    window.addEventListener('error', onError)
    window.addEventListener('unhandledrejection', onUnhandledRejection)
    return () => {
      window.removeEventListener('error', onError)
      window.removeEventListener('unhandledrejection', onUnhandledRejection)
    }
  }, [])
}

export function App() {
  useGlobalErrorLogging()

  return (
    <BrowserRouter>
      <AppRouter />
    </BrowserRouter>
  )
}
