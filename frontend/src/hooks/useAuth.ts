import { User, onAuthStateChanged, signInWithPopup, signOut } from 'firebase/auth'
import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { auth, googleProvider } from '../lib/firebase'

export type AuthState =
  | { status: 'loading' }
  | { status: 'unauthenticated' }
  | { status: 'authenticated_no_gmail'; user: User }
  | { status: 'ready'; user: User }

/**
 * Central auth hook.
 *
 * Status machine:
 *   loading → unauthenticated        (not signed in)
 *   loading → authenticated_no_gmail  (signed in, but Flow 2 not done)
 *   loading → ready                   (signed in + Gmail connected)
 *
 * authenticated_no_gmail → ready     after user completes Flow 2
 */
export function useAuth() {
  const [state, setState] = useState<AuthState>({ status: 'loading' })

  const checkGmailStatus = useCallback(async (user: User) => {
    try {
      const { gmail_connected } = await api<{ gmail_connected: boolean; uid: string }>(
        '/api/auth/status'
      )
      setState(
        gmail_connected
          ? { status: 'ready', user }
          : { status: 'authenticated_no_gmail', user }
      )
    } catch {
      // If backend is unreachable, still allow app to render
      setState({ status: 'authenticated_no_gmail', user })
    }
  }, [])

  useEffect(() => {
    const unsub = onAuthStateChanged(auth, user => {
      if (!user) {
        setState({ status: 'unauthenticated' })
        return
      }
      checkGmailStatus(user)
    })
    return unsub
  }, [checkGmailStatus])

  const signIn = useCallback(async () => {
    await signInWithPopup(auth, googleProvider)
  }, [])

  const signOutUser = useCallback(async () => {
    await signOut(auth)
    setState({ status: 'unauthenticated' })
  }, [])

  // Called after Flow 2 callback redirects back with ?gmail_connected=1
  const refreshGmailStatus = useCallback(() => {
    const user = auth.currentUser
    if (user) checkGmailStatus(user)
  }, [checkGmailStatus])

  return { state, signIn, signOut: signOutUser, refreshGmailStatus }
}
