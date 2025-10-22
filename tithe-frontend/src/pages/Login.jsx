import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import api, { loginUser } from '../api/api'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const from = location.state?.from?.pathname || '/user-dashboard'

  const onSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const res = await loginUser({ email, password })
      const token = res?.data?.token
      if (token) {
        localStorage.setItem('token', token)
        // Ensure subsequent requests immediately include the token
        api.defaults.headers.common.Authorization = `Bearer ${token}`
        alert('Welcome back')
        navigate(from, { replace: true })
      } else {
        alert('Login failed')
      }
    } catch (err) {
      const status = err?.response?.status
      if (status === 401) alert('Invalid credentials')
      else if (status === 500) alert('Server error')
      else alert('Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <h1 className="mb-6 text-3xl font-bold">Log in</h1>
      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label htmlFor="email" className="mb-1 block text-sm font-medium text-gray-700">Email</label>
          <input id="email" type="email" className="w-full rounded-md border px-3 py-2" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div>
          <label htmlFor="password" className="mb-1 block text-sm font-medium text-gray-700">Password</label>
          <input id="password" type="password" className="w-full rounded-md border px-3 py-2" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        <button type="submit" disabled={loading} className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-60">
          {loading ? 'Logging in...' : 'Log in'}
        </button>
      </form>
      <p className="mt-4 text-sm text-gray-600">
        No account? <Link className="text-blue-600 hover:underline" to="/signup">Sign up</Link>
      </p>
    </div>
  )
}
