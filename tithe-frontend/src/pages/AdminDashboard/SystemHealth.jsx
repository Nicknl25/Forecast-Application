import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import api from '../../api/api'

export default function SystemHealth() {
  const [health, setHealth] = useState({ container_uptime: '—', scheduler_status: 'unknown', jobs: [] })

  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const res = await api.get('/api/admin/system_health')
        if (active) setHealth(res.data)
      } catch {}
    }
    load()
    const id = setInterval(load, 60_000)
    return () => { active = false; clearInterval(id) }
  }, [])

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold">System Health</h2>
        <span className={`rounded-full px-2.5 py-0.5 text-xs ${health.scheduler_status === 'running' ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-700'}`}>{health.scheduler_status}</span>
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <div className="text-sm text-gray-600">Container Uptime</div>
        <div className="text-sm font-medium md:col-span-2">{health.container_uptime}</div>
        <div className="text-sm text-gray-600">Jobs</div>
        <div className="md:col-span-2 space-y-2">
          {health.jobs?.map((j, i) => (
            <div key={i} className="flex items-center justify-between text-sm">
              <div>{j.name}</div>
              <div className="text-gray-500">next: {j.next_run || '—'}</div>
              <div className="text-gray-500">status: {j.status}</div>
            </div>
          )) || <div className="text-sm text-gray-500">No jobs</div>}
        </div>
      </div>
    </motion.div>
  )
}

