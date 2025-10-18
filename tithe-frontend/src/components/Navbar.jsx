import { Link, NavLink, useNavigate } from 'react-router-dom'
import api from '../api/api'

export default function Navbar() {
  const navigate = useNavigate()
  const token = localStorage.getItem('token')
  const loggedIn = !!token

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
          <NavLink to="/dashboard" className={({ isActive }) => `rounded-md px-3 py-2 text-sm ${isActive ? 'bg-blue-600 text-white' : 'text-gray-700 hover:bg-gray-100'}`}>Dashboard</NavLink>
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
                to="/dashboard"
              >
                Dashboard
              </Link>
              <button
                onClick={() => {
                  localStorage.removeItem('token')
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
