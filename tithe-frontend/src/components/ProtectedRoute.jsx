import { Navigate, useLocation } from 'react-router-dom'

function decodeJwtClaims(token) {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return null
    const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const json = decodeURIComponent(
      atob(payload)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
    return JSON.parse(json)
  } catch (e) {
    return null
  }
}

export default function ProtectedRoute({ children }) {
  const token = localStorage.getItem('token')
  const location = useLocation()

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  // Lightweight client-side validation: ensure JWT structure and non-expired exp if present
  const claims = decodeJwtClaims(token)
  if (!claims) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }
  const now = Math.floor(Date.now() / 1000)
  if ((typeof claims.exp === 'number' && now >= claims.exp) || (typeof claims.nbf === 'number' && now < claims.nbf)) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  return children
}
