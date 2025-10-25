import { useEffect, useState } from 'react'
import api from '../../api/api'

export default function UserManagementTable() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({ name: '', email: '' })

  const load = async () => {
    try {
      setLoading(true)
      const res = await api.get('/api/admin/users')
      setRows(res.data)
    } catch {
      setRows([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const onAdd = async () => {
    try {
      await api.post('/api/admin/users/add', form)
      setShowAdd(false)
      setForm({ name: '', email: '' })
      load()
    } catch (e) {
      alert('Add failed')
    }
  }

  const onDelete = async (id) => {
    if (!confirm('Delete this user?')) return
    try {
      await api.delete(`/api/admin/users/${id}`)
      load()
    } catch {
      alert('Delete failed')
    }
  }

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">User Management</h2>
        <button onClick={() => setShowAdd(true)} className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700">Add User</button>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b bg-gray-50 text-gray-600">
            <tr>
              <th className="px-3 py-2 font-medium">ID</th>
              <th className="px-3 py-2 font-medium">Name</th>
              <th className="px-3 py-2 font-medium">Email</th>
              <th className="px-3 py-2 font-medium">Plan</th>
              <th className="px-3 py-2 font-medium">Role</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td className="px-3 py-3" colSpan="6">Loading…</td></tr>
            ) : rows.length ? rows.map((r) => (
              <tr key={r.id} className="border-b last:border-0">
                <td className="px-3 py-2">{r.id}</td>
                <td className="px-3 py-2">{r.name}</td>
                <td className="px-3 py-2">{r.email}</td>
                <td className="px-3 py-2">{r.plan}</td>
                <td className="px-3 py-2">{r.role}</td>
                <td className="px-3 py-2 text-right">
                  <button onClick={() => onDelete(r.id)} className="rounded-md bg-red-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-red-700">Delete</button>
                </td>
              </tr>
            )) : (
              <tr><td className="px-3 py-3" colSpan="6">No users</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showAdd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-sm rounded-xl bg-white p-5 shadow-lg">
            <h3 className="mb-3 text-lg font-semibold">Add User</h3>
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-sm text-gray-600">Name</label>
                <input className="w-full rounded-md border px-3 py-2 text-sm" value={form.name} onChange={(e) => setForm((s)=>({ ...s, name: e.target.value }))} />
              </div>
              <div>
                <label className="mb-1 block text-sm text-gray-600">Email</label>
                <input className="w-full rounded-md border px-3 py-2 text-sm" value={form.email} onChange={(e) => setForm((s)=>({ ...s, email: e.target.value }))} />
              </div>
            </div>
            <div className="mt-4 flex items-center justify-end gap-2">
              <button onClick={()=>setShowAdd(false)} className="rounded-md px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100">Cancel</button>
              <button onClick={onAdd} className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700">Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

