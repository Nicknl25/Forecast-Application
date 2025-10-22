import { Routes, Route, Navigate, Outlet } from 'react-router-dom'
import Navbar from './components/Navbar.jsx'
import Signup from './pages/Signup.jsx'
import Login from './pages/Login.jsx'
import UserDashboard from './pages/UserDashboard.jsx'
import TeamManagement from './pages/TeamManagement.jsx'
import AuditLog from './pages/AuditLog.jsx'
import Home from './pages/Home.jsx'
import Pricing from './pages/Pricing.jsx'
import About from './pages/About.jsx'
import Integrations from './pages/Integrations.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'

function Layout() {
  return (
    <div className="min-h-screen bg-white text-gray-800">
      <Navbar />
      <main className="container mx-auto px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/pricing" element={<Pricing />} />
        <Route path="/about" element={<About />} />
        <Route path="/integrations" element={<Integrations />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/login" element={<Login />} />
        <Route
          path="/user-dashboard"
          element={
            <ProtectedRoute>
              <UserDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/team-management"
          element={
            <ProtectedRoute>
              <TeamManagement />
            </ProtectedRoute>
          }
        />
        <Route
          path="/audit-log"
          element={
            <ProtectedRoute>
              <AuditLog />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Route>
    </Routes>
  )
}
