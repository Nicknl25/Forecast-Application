import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getCurrentUser, getQBAuthUrl } from '../api/api'

export default function Dashboard() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    const load = async () => {
      try {
        const res = await getCurrentUser()
        setUser(res.data)
      } catch (err) {
        const status = err?.response?.status
        if (status === 401) navigate('/login')
        else alert('Server error')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [navigate])

  const connectQB = async () => {
    try {
      alert('Connecting to QuickBooks…')
      const res = await getQBAuthUrl()
      const url = res?.data?.auth_url
      if (url) window.location.href = url
      else alert('Failed to get auth URL')
    } catch (err) {
      const status = err?.response?.status
      if (status === 401) navigate('/login')
      else alert('Server error')
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Dashboard</h1>
      {!loading && user && (
        <div className="rounded-md border p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Signed in as</p>
              <p className="text-lg font-medium">{user.company_name}</p>
            </div>
            <div className="text-sm text-gray-600">{user.email}</div>
          </div>
        </div>
      )}
      <button onClick={connectQB} className="rounded-md bg-emerald-500 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-600">
        Connect QuickBooks
      </button>
    </div>
  )
}

