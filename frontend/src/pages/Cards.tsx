import { AlertCircle, CreditCard, Plus, Trash2, KeyRound } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api, ApiError } from '../lib/api'

interface CardProvider {
  id: string
  name: string
  email_sender_pattern: string
  subject_keyword: string
}

export function Cards() {
  const [cards, setCards] = useState<CardProvider[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showAdd, setShowAdd] = useState(false)
  const [updatingPasswordFor, setUpdatingPasswordFor] = useState<string | null>(null)

  const fetchCards = async () => {
    setLoading(true)
    try {
      setCards(await api<CardProvider[]>('/api/cards'))
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load cards')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchCards() }, [])

  const deleteCard = async (id: string, name: string) => {
    if (!confirm(`Remove "${name}"? Existing transactions will not be deleted.`)) return
    try {
      await api(`/api/cards/${id}`, { method: 'DELETE' })
      setCards(prev => prev.filter(c => c.id !== id))
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete card')
    }
  }

  return (
    <div className="max-w-2xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Cards</h1>
          <p className="text-sm text-gray-500 mt-0.5">Manage your credit card providers</p>
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2 text-sm font-semibold text-white
                     hover:bg-brand-700 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Add card
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 rounded-lg px-4 py-3 mb-4">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
          <button className="ml-auto text-red-400 hover:text-red-600" onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {loading && (
        <div className="space-y-3">
          {[1, 2].map(i => <div key={i} className="h-20 rounded-xl bg-gray-100 animate-pulse" />)}
        </div>
      )}

      {!loading && cards.length === 0 && !showAdd && (
        <div className="text-center rounded-2xl border-2 border-dashed border-gray-200 py-12">
          <CreditCard className="h-8 w-8 text-gray-300 mx-auto mb-3" />
          <p className="text-sm text-gray-500">No cards added yet</p>
          <button onClick={() => setShowAdd(true)} className="mt-3 text-sm text-brand-600 hover:text-brand-700 font-medium">
            + Add your first card
          </button>
        </div>
      )}

      <div className="space-y-3">
        {cards.map(card => (
          <div key={card.id} className="bg-white rounded-xl border border-gray-200 px-5 py-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-brand-50">
                  <CreditCard className="h-5 w-5 text-brand-600" />
                </div>
                <div>
                  <p className="font-semibold text-gray-900">{card.name}</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    from: {card.email_sender_pattern} · subject: "{card.subject_keyword}"
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={() => setUpdatingPasswordFor(card.id)}
                  title="Update PDF password"
                  className="p-1.5 text-gray-400 hover:text-brand-600 hover:bg-brand-50 rounded-lg transition-colors"
                >
                  <KeyRound className="h-4 w-4" />
                </button>
                <button
                  onClick={() => deleteCard(card.id, card.name)}
                  title="Remove card"
                  className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>

            {updatingPasswordFor === card.id && (
              <UpdatePasswordForm
                providerId={card.id}
                onClose={() => setUpdatingPasswordFor(null)}
                onError={setError}
              />
            )}
          </div>
        ))}
      </div>

      {showAdd && (
        <AddCardForm
          onAdded={card => { setCards(prev => [...prev, card]); setShowAdd(false) }}
          onClose={() => setShowAdd(false)}
          onError={setError}
        />
      )}
    </div>
  )
}

function AddCardForm({
  onAdded,
  onClose,
  onError,
}: {
  onAdded: (card: CardProvider) => void
  onClose: () => void
  onError: (msg: string) => void
}) {
  const [form, setForm] = useState({ name: '', email_sender_pattern: '', subject_keyword: '', password: '' })
  const [saving, setSaving] = useState(false)

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm(prev => ({ ...prev, [k]: e.target.value }))

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      const card = await api<CardProvider>('/api/cards', {
        method: 'POST',
        body: JSON.stringify(form),
      })
      onAdded(card)
    } catch (err: unknown) {
      onError(err instanceof ApiError ? err.message : 'Failed to add card')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={submit} className="mt-4 bg-white rounded-xl border border-gray-200 px-5 py-5 space-y-4">
      <h3 className="font-semibold text-gray-900">Add card provider</h3>

      {[
        { label: 'Card name', key: 'name', placeholder: 'HDFC Regalia', type: 'text' },
        { label: 'Sender email / domain', key: 'email_sender_pattern', placeholder: '@hdfcbank.com', type: 'text' },
        { label: 'Subject keyword', key: 'subject_keyword', placeholder: 'credit card statement', type: 'text' },
        { label: 'PDF password', key: 'password', placeholder: 'Statement password', type: 'password' },
      ].map(({ label, key, placeholder, type }) => (
        <div key={key}>
          <label className="block text-xs font-medium text-gray-700 mb-1">{label}</label>
          <input
            type={type}
            required
            value={form[key as keyof typeof form]}
            onChange={set(key)}
            placeholder={placeholder}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
      ))}

      <p className="text-xs text-gray-400">
        The PDF password is encrypted before storage and never logged.
      </p>

      <div className="flex gap-3 justify-end">
        <button type="button" onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700">
          Cancel
        </button>
        <button
          type="submit"
          disabled={saving}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white
                     hover:bg-brand-700 disabled:opacity-50 transition-colors"
        >
          {saving ? 'Saving…' : 'Save card'}
        </button>
      </div>
    </form>
  )
}

function UpdatePasswordForm({
  providerId,
  onClose,
  onError,
}: {
  providerId: string
  onClose: () => void
  onError: (msg: string) => void
}) {
  const [password, setPassword] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      await api(`/api/cards/${providerId}/password`, {
        method: 'PUT',
        body: JSON.stringify({ password }),
      })
      onClose()
    } catch (err: unknown) {
      onError(err instanceof ApiError ? err.message : 'Failed to update password')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={submit} className="mt-3 flex gap-2 items-end">
      <div className="flex-1">
        <label className="block text-xs font-medium text-gray-600 mb-1">New PDF password</label>
        <input
          type="password"
          required
          value={password}
          onChange={e => setPassword(e.target.value)}
          placeholder="Enter new password"
          className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
      </div>
      <button
        type="submit"
        disabled={saving}
        className="rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-medium text-white
                   hover:bg-brand-700 disabled:opacity-50 transition-colors"
      >
        {saving ? 'Saving…' : 'Update'}
      </button>
      <button type="button" onClick={onClose} className="text-sm text-gray-400 hover:text-gray-600 px-1">
        Cancel
      </button>
    </form>
  )
}
