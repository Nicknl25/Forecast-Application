import api from '../../api/api'
import { useState } from 'react'

export default function AdminActions() {
  const [busy, setBusy] = useState(false)

  const run = async (job) => {
    try {
      setBusy(true)
      await api.post('/api/admin/run_job', { job })
      alert(`Started ${job}`)
    } catch {
      alert('Failed to start job')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Admin Actions</h2>
      </div>
      <div className="flex flex-wrap gap-3">
        <button disabled={busy} onClick={()=>run('token_refresh')} className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-60 hover:bg-blue-700">Run Token Refresh</button>
        <button disabled={busy} onClick={()=>run('daily_sync')} className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-60 hover:bg-blue-700">Run Daily Sync</button>
      </div>
    </div>
  )
}

