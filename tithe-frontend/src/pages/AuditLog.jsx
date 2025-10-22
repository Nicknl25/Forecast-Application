import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { getAuditLog, getCompanyUsers, getCurrentUser } from '../api/api'

export default function AuditLog() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [email, setEmail] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const navigate = useNavigate()

  const fetchEvents = async (filters = {}) => {
    setLoading(true)
    try {
      const res = await getAuditLog(filters)
      const payload = res?.data
      const list = Array.isArray(payload) ? payload : (payload?.events || [])
      const sorted = [...list].sort((a, b) => {
        const da = new Date(a.timestamp || a.created_at || 0).getTime()
        const db = new Date(b.timestamp || b.created_at || 0).getTime()
        return db - da
      })
      setEvents(sorted)
    } catch (err) {
      const status = err?.response?.status
      if (status === 401) navigate('/login')
      else if (status === 403) navigate('/user-dashboard', { replace: true })
      else alert('Failed to load audit log')
    } finally {
      setLoading(false)
    }
  }

  const clearFilters = async () => {
    setEmail('')
    setStart('')
    setEnd('')
    await fetchEvents({})
  }

  const exportCsv = () => {
    try {
      const headers = ['Timestamp', 'User Email', 'Action', 'Details']
      const escape = (val) => {
        const s = (val ?? '').toString()
        // Escape double quotes and wrap in quotes to be safe for commas/newlines
        return '"' + s.replace(/"/g, '""') + '"'
      }
      const rows = events.map((e) => [
        e.timestamp || e.created_at || '',
        e.user_email || '',
        e.action || '',
        e.details || '',
      ])
      const csv = [headers.map(escape).join(','), ...rows.map((r) => r.map(escape).join(','))].join('\r\n')
      const bom = '\ufeff' // Excel-friendly BOM
      const blob = new Blob([bom + csv], { type: 'text/csv;charset=utf-8;' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      const date = new Date().toISOString().slice(0, 10)
      a.href = url
      a.download = `audit_log_${date}.csv`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e) {
      alert('Failed to export CSV')
    }
  }

  useEffect(() => {
    const init = async () => {
      try {
        const meRes = await getCurrentUser()
        const usersRes = await getCompanyUsers()
        const me = meRes?.data
        const users = usersRes?.data?.users || []
        const myRole = users.find((u) => u.id === me?.user_id)?.role
        if (myRole !== 'Owner' && myRole !== 'Admin') {
          navigate('/user-dashboard', { replace: true })
          return
        }
        await fetchEvents({})
      } catch (err) {
        const status = err?.response?.status
        if (status === 401) navigate('/login')
        else if (status === 403) navigate('/user-dashboard', { replace: true })
        else alert('Failed to load audit log')
        setLoading(false)
      }
    }
    init()
  }, [navigate])

  return (
    <div className="space-y-6">
      <div className="sticky top-0 z-10 flex items-center justify-between bg-white/70 backdrop-blur p-2 rounded-md">
        <h1 className="text-3xl font-bold tracking-tight">Audit Log</h1>
        <button
          type="button"
          onClick={() => navigate('/user-dashboard')}
          className="rounded-md bg-gray-100 px-3 py-2 text-sm font-medium text-gray-900 ring-1 ring-inset ring-gray-300 hover:bg-gray-200"
        >
          Back to Dashboard
        </button>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="rounded-2xl border border-gray-200 bg-white/60 p-6 shadow-sm backdrop-blur"
      >
        {/* Filters */}
        <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-4">
          <div className="flex flex-col">
            <label className="mb-1 block text-sm text-gray-600">From</label>
            <input
              type="date"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              value={start}
              onChange={(e) => setStart(e.target.value)}
            />
          </div>
          <div className="flex flex-col">
            <label className="mb-1 block text-sm text-gray-600">To</label>
            <input
              type="date"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
            />
          </div>
          <div className="flex flex-col md:col-span-2">
            <label className="mb-1 block text-sm text-gray-600">User Email</label>
            <input
              type="email"
              placeholder="user@example.com"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="md:col-span-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={clearFilters}
              disabled={loading}
              className="rounded-md bg-gray-100 px-4 py-2 text-sm font-medium text-gray-800 ring-1 ring-inset ring-gray-300 hover:bg-gray-200 disabled:opacity-60"
            >
              Clear Filters
            </button>
            <button
              type="button"
              onClick={exportCsv}
              disabled={loading || events.length === 0}
              className="rounded-md bg-gray-100 px-4 py-2 text-sm font-medium text-gray-800 ring-1 ring-inset ring-gray-300 hover:bg-gray-200 disabled:opacity-60"
            >
              Export CSV
            </button>
            <button
              type="button"
              onClick={() => fetchEvents({ email: email || undefined, start: start || undefined, end: end || undefined })}
              disabled={loading}
              aria-busy={loading}
              className="rounded-md bg-emerald-500 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-60"
            >
              {loading ? 'Searching…' : 'Search'}
            </button>
          </div>
        </div>

        {/* Scrollable table */}
        <div className="overflow-hidden rounded-xl border">
          <div className="max-h-[600px] overflow-y-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="sticky top-0 bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left font-medium text-gray-600">Timestamp</th>
                  <th className="px-4 py-2 text-left font-medium text-gray-600">User Email</th>
                  <th className="px-4 py-2 text-left font-medium text-gray-600">Action</th>
                  <th className="px-4 py-2 text-left font-medium text-gray-600">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {!loading && events.map((e, idx) => (
                  <tr key={idx} className="hover:bg-gray-50/70">
                    <td className="px-4 py-2">{e.timestamp || e.created_at || '—'}</td>
                    <td className="px-4 py-2 text-gray-700">{e.user_email || '—'}</td>
                    <td className="px-4 py-2">{e.action || '—'}</td>
                    <td className="px-4 py-2 text-gray-600">{e.details || '—'}</td>
                  </tr>
                ))}
                {!loading && events.length === 0 && (
                  <tr>
                    <td className="px-4 py-6 text-center text-gray-500" colSpan={4}>No results found</td>
                  </tr>
                )}
                {loading && (
                  <tr>
                    <td className="px-4 py-6 text-center text-gray-500" colSpan={4}>Loading…</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </motion.div>
    </div>
  )
}
