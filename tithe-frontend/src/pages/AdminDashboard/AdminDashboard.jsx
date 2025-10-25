import { motion } from 'framer-motion'
import BusinessOverview from './BusinessOverview.jsx'
import SystemHealth from './SystemHealth.jsx'
import UserManagementTable from './UserManagementTable.jsx'
import PaymentManagement from './PaymentManagement.jsx'
import LogFeed from './LogFeed.jsx'
import AdminActions from './AdminActions.jsx'

export default function AdminDashboard() {
  return (
    <div className="space-y-8">
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
        <h1 className="text-3xl font-bold tracking-tight">Admin Command Center</h1>
        <p className="text-sm text-gray-600">Mission Control for business and system operations</p>
      </motion.div>

      <BusinessOverview />
      <SystemHealth />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <UserManagementTable />
        <PaymentManagement />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <LogFeed />
        <AdminActions />
      </div>
    </div>
  )
}

