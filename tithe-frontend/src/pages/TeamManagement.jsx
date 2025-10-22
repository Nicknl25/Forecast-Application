import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  getCurrentUser,
  getCompanyUsers,
  addCompanyUser,
  deleteCompanyUser,
  updateCompanyUser,
} from '../api/api'

function Modal({ open, title, children, onClose }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative w-full max-w-lg rounded-2xl bg-white shadow-xl ring-1 ring-black/5">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h3 className="text-lg font-semibold">{title}</h3>
          <button className="rounded-md p-2 text-gray-500 hover:bg-gray-100" onClick={onClose}>
            <span className="sr-only">Close</span>
            A-
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
      </div>
    </div>
  )
}

export default function TeamManagement() {
  const [me, setMe] = useState(null)
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [addOpen, setAddOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [pendingDeleteId, setPendingDeleteId] = useState(null)

  const [newUser, setNewUser] = useState({ name: '', email: '', role: 'Member' })
  const [editUser, setEditUser] = useState({ id: null, name: '', email: '', role: 'Member' })

  const navigate = useNavigate()

  const loadAll = async () => {
    try {
      const meRes = await getCurrentUser()
      setMe(meRes.data)
      const list = await getCompanyUsers()
      setUsers(list.data?.users || [])
    } catch (err) {
      const status = err?.response?.status
      if (status === 401) navigate('/login')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Optional: restore scroll position for this page
  useEffect(() => {
    try {
      const saved = Number(sessionStorage.getItem('scroll_team_management') || '0')
      if (saved > 0) {
        window.scrollTo(0, saved)
      }
    } catch {}
  }, [])

  const handleAddUser = async (e) => {
    e.preventDefault()
    try {
      if (!newUser.email) return
      const exists = users.some((u) => (u.email || '').toLowerCase() === newUser.email.toLowerCase())
      if (exists) {
        alert('User already part of company')
        return
      }
      await addCompanyUser(newUser)
      const list = await getCompanyUsers()
      setUsers(list.data?.users || [])
      setAddOpen(false)
      setNewUser({ name: '', email: '', role: 'Member' })
    } catch (err) {
      const status = err?.response?.status
      if (status === 401) navigate('/login')
      else alert(err?.response?.data?.error || 'Failed to add user')
    }
  }

  const askRemove = (id) => {
    setPendingDeleteId(id)
    setConfirmOpen(true)
  }

  const startEdit = (u) => {
    setEditUser({ id: u.id, name: u.name || '', email: u.email || '', role: u.role || 'Member' })
    setEditOpen(true)
  }

  const handleRemove = async () => {
    if (!pendingDeleteId) return
    try {
      await deleteCompanyUser(pendingDeleteId)
      setUsers((prevList) => prevList.filter((u) => u.id !== pendingDeleteId))
    } catch (err) {
      const status = err?.response?.status
      if (status === 401) navigate('/login')
      else alert(err?.response?.data?.error || 'Failed to remove user')
    } finally {
      setConfirmOpen(false)
      setPendingDeleteId(null)
    }
  }

  const handleSaveEdit = async (e) => {
    e.preventDefault()
    try {
      if (!editUser?.id) return
      await updateCompanyUser(editUser.id, { name: editUser.name, email: editUser.email, role: editUser.role })
      const list = await getCompanyUsers()
      setUsers(list.data?.users || [])
      setEditOpen(false)
    } catch (err) {
      const status = err?.response?.status
      if (status === 401) navigate('/login')
      else alert(err?.response?.data?.error || 'Failed to update user')
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Team Management</h1>
          {!loading && me && (
            <div className="text-sm text-gray-600">Signed in as {me.company_name} ({me.email})</div>
          )}
        </div>
        <button
          type="button"
          onClick={() => {
            try { sessionStorage.setItem('scroll_team_management', String(window.scrollY || 0)) } catch {}
            navigate('/user-dashboard')
          }}
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
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Team Members</h2>
          <button
            className="rounded-md bg-emerald-500 px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-emerald-600"
            onClick={() => setAddOpen(true)}
          >
            Add User
          </button>
        </div>
        <div className="overflow-hidden rounded-xl border">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-gray-600">Name</th>
                <th className="px-4 py-2 text-left font-medium text-gray-600">Email</th>
                <th className="px-4 py-2 text-left font-medium text-gray-600">Role</th>
                <th className="px-4 py-2 text-left font-medium text-gray-600">Last Login</th>
                <th className="px-4 py-2 text-left font-medium text-gray-600">Status</th>
                <th className="px-4 py-2 text-right font-medium text-gray-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-gray-50/70">
                  <td className="px-4 py-2">{u.name}</td>
                  <td className="px-4 py-2 text-gray-700">{u.email}</td>
                  <td className="px-4 py-2">{u.role}</td>
                  <td className="px-4 py-2 text-gray-500">{u.last_login || '—'}</td>
                  <td className="px-4 py-2">
                    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      (u.status || 'Active') === 'Active'
                        ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200'
                        : 'bg-amber-50 text-amber-700 ring-1 ring-amber-200'
                    }`}>{u.status}</span>
                  </td>
                  <td className="px-4 py-2 text-right space-x-2">
                    <button
                      className="rounded-md px-2 py-1 text-sm text-gray-700 ring-1 ring-gray-300 hover:bg-gray-50"
                      onClick={() => startEdit(u)}
                    >
                      Edit
                    </button>
                    <button
                      className="rounded-md px-2 py-1 text-sm text-rose-600 hover:bg-rose-50"
                      onClick={() => askRemove(u.id)}
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
              {users.length === 0 && (
                <tr>
                  <td className="px-4 py-6 text-center text-gray-500" colSpan={6}>No users yet</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </motion.div>

      {/* Add User Modal */}
      <Modal open={addOpen} title="Add New User" onClose={() => setAddOpen(false)}>
        <form onSubmit={handleAddUser} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm text-gray-600">Name</label>
            <input
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-emerald-500 focus:outline-none"
              value={newUser.name}
              onChange={(e) => setNewUser((s) => ({ ...s, name: e.target.value }))}
              placeholder="Jane Doe"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-gray-600">Email</label>
            <input
              type="email"
              required
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-emerald-500 focus:outline-none"
              value={newUser.email}
              onChange={(e) => setNewUser((s) => ({ ...s, email: e.target.value }))}
              placeholder="jane@acme.com"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-gray-600">Role</label>
            <select
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-emerald-500 focus:outline-none"
              value={newUser.role}
              onChange={(e) => setNewUser((s) => ({ ...s, role: e.target.value }))}
            >
              <option>Member</option>
              <option>Admin</option>
              <option>Analyst</option>
            </select>
          </div>
          <div className="flex justify-end gap-2">
            <button type="button" className="rounded-md px-4 py-2 text-sm text-gray-700 hover:bg-gray-100" onClick={() => setAddOpen(false)}>Cancel</button>
            <button type="submit" className="rounded-md bg-emerald-500 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-600">Add User</button>
          </div>
        </form>
      </Modal>

      {/* Edit User Modal */}
      <Modal open={editOpen} title="Edit User" onClose={() => setEditOpen(false)}>
        <form onSubmit={handleSaveEdit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm text-gray-600">Name</label>
            <input
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-emerald-500 focus:outline-none"
              value={editUser.name}
              onChange={(e) => setEditUser((s) => ({ ...s, name: e.target.value }))}
              placeholder="Jane Doe"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-gray-600">Email</label>
            <input
              type="email"
              required
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-emerald-500 focus:outline-none"
              value={editUser.email}
              onChange={(e) => setEditUser((s) => ({ ...s, email: e.target.value }))}
              placeholder="jane@acme.com"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-gray-600">Role</label>
            <select
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-emerald-500 focus:outline-none"
              value={editUser.role}
              onChange={(e) => setEditUser((s) => ({ ...s, role: e.target.value }))}
            >
              <option>Member</option>
              <option>Admin</option>
              <option>Owner</option>
              <option>Analyst</option>
            </select>
          </div>
          <div className="flex justify-end gap-2">
            <button type="button" className="rounded-md px-4 py-2 text-sm text-gray-700 hover:bg-gray-100" onClick={() => setEditOpen(false)}>Cancel</button>
            <button type="submit" className="rounded-md bg-emerald-500 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-600">Save</button>
          </div>
        </form>
      </Modal>

      {/* Confirm Remove Modal */}
      <Modal open={confirmOpen} title="Remove User" onClose={() => setConfirmOpen(false)}>
        <div className="space-y-4">
          <p className="text-sm text-gray-700">Are you sure you want to remove this user from the company?</p>
          <div className="flex justify-end gap-2">
            <button className="rounded-md px-4 py-2 text-sm text-gray-700 hover:bg-gray-100" onClick={() => setConfirmOpen(false)}>Cancel</button>
            <button className="rounded-md bg-rose-600 px-4 py-2 text-sm font-medium text-white hover:bg-rose-700" onClick={handleRemove}>Remove</button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
