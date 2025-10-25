import { useEffect, useState } from 'react'
import api from '../../api/api'

export default function PaymentManagement() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)

  const load = async () => {
    try {
      setLoading(true)
      const res = await api.get('/api/admin/payments')
      setRows(res.data)
    } catch {
      setRows([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const retry = async (id) => {
    try {
      await api.post(`/api/admin/payments/retry/${id}`)
      alert('Retry triggered')
    } catch {
      alert('Retry failed')
    }
  }

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Payment Management</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b bg-gray-50 text-gray-600">
            <tr>
              <th className="px-3 py-2 font-medium">Client</th>
              <th className="px-3 py-2 font-medium">Provider</th>
              <th className="px-3 py-2 font-medium">Plan</th>
              <th className="px-3 py-2 font-medium">Monthly</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 font-medium">Last</th>
              <th className="px-3 py-2 font-medium">Next</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td className="px-3 py-3" colSpan="8">Loading…</td></tr>
            ) : rows.length ? rows.map((r) => (
              <tr key={r.id} className="border-b last:border-0">
                <td className="px-3 py-2">{r.email || '—'}</td>
                <td className="px-3 py-2">{r.provider}</td>
                <td className="px-3 py-2">{r.plan}</td>
                <td className="px-3 py-2">${Number(r.monthly_fee || 0).toFixed(2)}</td>
                <td className="px-3 py-2">{r.status}</td>
                <td className="px-3 py-2">{r.last_payment_date || '—'}</td>
                <td className="px-3 py-2">{r.next_payment_due || '—'}</td>
                <td className="px-3 py-2 text-right">
                  <button onClick={()=>retry(r.id)} className="rounded-md bg-blue-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-blue-700">Retry Payment</button>
                </td>
              </tr>
            )) : (
              <tr><td className="px-3 py-3" colSpan="8">No subscriptions</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

