import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import api from '../../api/api'

function StatCard({ title, value, icon }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm text-gray-500">{title}</div>
          <div className="mt-1 text-2xl font-semibold">{value}</div>
        </div>
        <div className="text-gray-400">{icon}</div>
      </div>
    </div>
  )
}

export default function BusinessOverview() {
  const [data, setData] = useState({ total_clients: 0, paying_clients: 0, mrr: 0, arpu: 0 })

  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const res = await api.get('/api/admin/business_summary')
        if (active) setData(res.data)
      } catch {}
    }
    load()
    const id = setInterval(load, 60_000)
    return () => { active = false; clearInterval(id) }
  }, [])

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Total Clients" value={data.total_clients} icon={<span>👥</span>} />
        <StatCard title="Paying Clients" value={data.paying_clients} icon={<span>💳</span>} />
        <StatCard title="MRR" value={`$${Number(data.mrr).toFixed(2)}`} icon={<span>$</span>} />
        <StatCard title="ARPU" value={`$${Number(data.arpu).toFixed(2)}`} icon={<span>📈</span>} />
      </div>
    </motion.div>
  )
}

