import { useCallback, useMemo, useState } from 'react'
import { getQBAuthUrl } from '../api/api'

export default function Integrations() {
  const [connecting, setConnecting] = useState(false)

  const providers = useMemo(() => ([
    { key: 'quickbooks', name: 'QuickBooks', description: 'Connect your QuickBooks account to sync data.' },
    { key: 'xero', name: 'Xero', description: 'Connect your Xero account to sync data.' },
    { key: 'freshbooks', name: 'FreshBooks', description: 'Connect your FreshBooks account to sync data.' },
  ]), [])

  const connectQuickBooks = useCallback(async () => {
    try {
      setConnecting(true)
      // Try to start onboarding if already connected; otherwise fall back to OAuth
      try {
        const r = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/integrations/start_onboarding`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('token') || ''}`,
          },
        })
        if (r.ok) {
          const data = await r.json().catch(() => ({}))
          if (data?.already_onboarded) alert('QuickBooks already onboarded.')
          else alert('Onboarding started. You can monitor progress in logs.')
          return
        }
      } catch {}

      // Not connected: begin OAuth connect
      const res = await getQBAuthUrl()
      const url = res?.data?.auth_url
      if (url) {
        window.location.href = url
      } else {
        alert('Failed to initiate QuickBooks connect')
      }
    } catch (err) {
      const status = err?.response?.status
      if (status === 401) {
        alert('Session expired. Please log in again.')
      } else {
        alert('Server error while connecting QuickBooks')
      }
    } finally {
      setConnecting(false)
    }
  }, [])

  // No automatic triggers; user starts via click

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Integrations</h1>
      {connecting && (
        <div className="rounded-md border border-blue-200 bg-blue-50 p-3 text-sm text-blue-700">
          Redirecting to QuickBooks…
        </div>
      )}
      <div className="grid gap-6 md:grid-cols-3">
        {providers.map((p) => (
          <div key={p.key} className="rounded-lg border bg-white p-6 shadow-sm">
            <h3 className="mb-2 text-lg font-semibold">{p.name}</h3>
            <p className="mb-4 text-gray-600">{p.description}</p>
            {p.key === 'quickbooks' ? (
              <button onClick={connectQuickBooks} disabled={connecting} className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60">
                {connecting ? 'Connecting…' : 'Connect'}
              </button>
            ) : (
              <button onClick={() => alert(`${p.name} connect placeholder`)} className="rounded-md bg-gray-300 px-4 py-2 text-sm font-medium text-white cursor-not-allowed" title="Coming soon">
                Coming Soon
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
