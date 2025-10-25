import { useEffect, useState } from 'react'
import api from '../../api/api'

export default function LogFeed() {
  const [lines, setLines] = useState([])

  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const res = await api.get('/api/admin/logs')
        if (active) setLines(res.data?.lines || [])
      } catch {}
    }
    load()
    const id = setInterval(load, 15_000)
    return () => { active = false; clearInterval(id) }
  }, [])

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Logs</h2>
      </div>
      <div className="h-64 overflow-auto rounded-md bg-black p-3 text-xs text-green-200">
        {lines.length ? lines.map((l, i) => (
          <div key={i} className="font-mono leading-relaxed">{l}</div>
        )) : <div className="text-gray-400">No log lines</div>}
      </div>
    </div>
  )
}

