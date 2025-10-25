import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { registerUser } from '../api/api'

export default function Signup() {
  const [companyName, setCompanyName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const onSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      await registerUser({ company_name: companyName, email, password })
      alert('Account created. Please log in to continue.')
      // Redirect to login; onboarding check runs after login
      navigate('/login', { replace: true })
    } catch (err) {
      const status = err?.response?.status
      const msg = err?.response?.data?.error || 'Registration failed'
      if (status === 500) alert('Server error')
      else alert(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <h1 className="mb-6 text-3xl font-bold">Sign up</h1>
      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label htmlFor="company" className="mb-1 block text-sm font-medium text-gray-700">Company Name</label>
          <input id="company" className="w-full rounded-md border px-3 py-2" value={companyName} onChange={(e) => setCompanyName(e.target.value)} required />
        </div>
        <div>
          <label htmlFor="email" className="mb-1 block text-sm font-medium text-gray-700">Email</label>
          <input id="email" type="email" className="w-full rounded-md border px-3 py-2" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div>
          <label htmlFor="password" className="mb-1 block text-sm font-medium text-gray-700">Password</label>
          <input id="password" type="password" className="w-full rounded-md border px-3 py-2" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        <button type="submit" disabled={loading} className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-60">
          {loading ? 'Creating...' : 'Create account'}
        </button>
      </form>
      <p className="mt-4 text-sm text-gray-600">
        Already have an account? <Link className="text-blue-600 hover:underline" to="/login">Log in</Link>
      </p>
    </div>
  )
}
