import { Link, NavLink, useNavigate } from 'react-router-dom'
import api, { getCurrentUser } from '../api/api'
import { useEffect, useState } from 'react'

export default function Navbar() {
  const navigate = useNavigate()
  const token = localStorage.getItem('token')
  const loggedIn = !!token
  const [isAdmin, setIsAdmin] = useState(() => (localStorage.getItem('is_admin') === '1' || localStorage.getItem('is_admin') === 'true'))

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      if (!loggedIn) return
      try {
        const res = await getCurrentUser()
        const flag = !!res?.data?.is_admin
        localStorage.setItem('is_admin', flag ? '1' : '0')
        if (!cancelled) setIsAdmin(flag)
      } catch {}
    }
    load()
    return () => { cancelled = true }
  }, [loggedIn])

  return (
    <header className="border-b bg-white">
      <div className="container mx-auto flex items-center justify-between px-4 py-3">
        <Link to="/" className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-md bg-gradient-to-br from-blue-600 to-emerald-500" />
          <span className="text-lg font-semibold">Tithe Financial</span>
        </Link>
        <nav className="hidden items-center gap-2 md:flex">
          <NavLink to="/pricing" className={({ isActive }) => `rounded-md px-3 py-2 text-sm ${isActive ? 'bg-blue-600 text-white' : 'text-gray-700 hover:bg-gray-100'}`}>Pricing</NavLink>
          <NavLink to="/about" className={({ isActive }) => `rounded-md px-3 py-2 text-sm ${isActive ? 'bg-blue-600 text-white' : 'text-gray-700 hover:bg-gray-100'}`}>About</NavLink>
          <NavLink to="/integrations" className={({ isActive }) => `rounded-md px-3 py-2 text-sm ${isActive ? 'bg-blue-600 text-white' : 'text-gray-700 hover:bg-gray-100'}`}>Integrations</NavLink>
          <NavLink to="/financial-analysis" className={({ isActive }) => `rounded-md px-3 py-2 text-sm ${isActive ? 'bg-blue-600 text-white' : 'text-gray-700 hover:bg-gray-100'}`}>Financial Analysis</NavLink>
          <NavLink to="/user-dashboard" className={({ isActive }) => `rounded-md px-3 py-2 text-sm ${isActive ? 'bg-blue-600 text-white' : 'text-gray-700 hover:bg-gray-100'}`}>User Dashboard</NavLink>
          <NavLink to="/team-management" className={({ isActive }) => `rounded-md px-3 py-2 text-sm ${isActive ? 'bg-blue-600 text-white' : 'text-gray-700 hover:bg-gray-100'}`}>Team Management</NavLink>
          {loggedIn && isAdmin && (
            <NavLink to="/admin-dashboard" className={({ isActive }) => `rounded-md px-3 py-2 text-sm ${isActive ? 'bg-blue-600 text-white' : 'text-gray-700 hover:bg-gray-100'}`}>Admin</NavLink>
          )}
        </nav>
        <nav className="flex items-center gap-2">
          {!loggedIn ? (
            <>
              <Link className="rounded-md px-3 py-2 text-sm hover:bg-gray-100" to="/login">
                Login
              </Link>
              <Link
                className="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
                to="/signup"
              >
                Signup
              </Link>
            </>
          ) : (
            <>
              <Link
                className="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
                to="/user-dashboard"
              >
                User Dashboard
              </Link>
              <button
                onClick={() => {
                  localStorage.removeItem('token')
                  localStorage.removeItem('is_admin')
                  delete api.defaults.headers.common.Authorization
                  navigate('/')
                }}
                className="rounded-md bg-gray-100 px-3 py-2 text-sm font-medium hover:bg-gray-200"
              >
                Logout
              </button>
            </>
          )}
        </nav>
      </div>
    </header>
  )
}
