import { useEffect, useMemo, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { getCurrentUser, getCompanyInfo, getCompanyUsers, updateCompanySettings } from '../api/api'

export default function UserDashboard() {
  const [me, setMe] = useState(null)
  const [info, setInfo] = useState(null)
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const [settings, setSettings] = useState({ company_name: '', industry: '', timezone: '', currency: '', address: '', phone: '', email: '' })

  const navigate = useNavigate()

  const loadAll = async () => {
    try {
      const meRes = await getCurrentUser()
      setMe(meRes.data)
      const [infoRes, usersRes] = await Promise.all([getCompanyInfo(), getCompanyUsers()])
      setInfo(infoRes.data)
      setUsers(usersRes.data?.users || [])
      setSettings((prev) => ({
        ...prev,
        company_name: infoRes.data?.company_name || '',
        industry: infoRes.data?.industry || '',
        timezone: infoRes.data?.timezone || '',
        currency: infoRes.data?.currency || '',
        address: infoRes.data?.address || '',
        phone: infoRes.data?.phone || '',
        email: infoRes.data?.email || '',
      }))
    } catch (err) {
      const status = err?.response?.status
      if (status === 401) navigate('/login')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Optional: restore scroll position when returning to this page
  useEffect(() => {
    try {
      const saved = Number(sessionStorage.getItem('scroll_user_dashboard') || '0')
      if (saved > 0) {
        window.scrollTo(0, saved)
      }
    } catch {}
  }, [])

  const handleSaveSettings = async () => {
    try {
      setSaving(true)
      const res = await updateCompanySettings(settings)
      const data = res.data
      setInfo((prev) => ({
        ...(prev || {}),
        company_name: data.company_name,
        industry: data.industry,
        timezone: data.timezone,
        currency: data.currency,
        address: data.address,
        phone: data.phone,
        email: data.email,
      }))
    } catch (err) {
      alert(err?.response?.data?.error || 'Failed to save settings')
    } finally {
      setSaving(false)
    }
  }

  const cards = useMemo(() => ([
    { key: 'overview', delay: 0.0 },
    { key: 'billing', delay: 0.05 },
    { key: 'settings', delay: 0.1 },
    { key: 'security', delay: 0.15 },
  ]), [])

  const INDUSTRIES = [
    'Nonprofit','Technology','Healthcare','Finance','Education','Retail','Manufacturing','Professional Services','Construction','Real Estate','Transportation','Hospitality','Media','Government','Energy','Agriculture','Logistics','Legal','Insurance','Consulting'
  ]

  const TIMEZONES = [
    'UTC','America/New_York','America/Chicago','America/Denver','America/Los_Angeles','America/Phoenix','America/Anchorage','Pacific/Honolulu','America/Toronto','America/Vancouver','America/Mexico_City','America/Bogota','America/Sao_Paulo','America/Argentina/Buenos_Aires','Europe/London','Europe/Paris','Europe/Berlin','Europe/Madrid','Europe/Rome','Europe/Amsterdam','Europe/Brussels','Europe/Zurich','Europe/Stockholm','Europe/Oslo','Europe/Copenhagen','Europe/Warsaw','Europe/Prague','Europe/Budapest','Europe/Bucharest','Europe/Athens','Europe/Kyiv','Africa/Johannesburg','Asia/Tokyo','Asia/Seoul','Asia/Shanghai','Asia/Hong_Kong','Asia/Singapore','Asia/Kuala_Lumpur','Asia/Bangkok','Asia/Jakarta','Asia/Manila','Asia/Kolkata','Australia/Sydney','Australia/Melbourne','Australia/Perth'
  ]

  const CURRENCIES = [
    'USD','EUR','GBP','CAD','AUD','NZD','JPY','CNY','INR','CHF','SEK','NOK','DKK','PLN','CZK','HUF','RON','ZAR','BRL','MXN','ARS','CLP','COP','PEN','HKD','SGD','MYR','IDR','THB','VND','PHP','AED','SAR','TRY','KRW','ILS'
  ]

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">User Dashboard</h1>
        {!loading && me && (
          <div className="text-sm text-gray-600">Signed in as {me.company_name} ({me.email})</div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Company Overview (top-right on desktop) */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: cards[0].delay }}
          className="rounded-2xl border border-gray-200 bg-white/60 p-6 shadow-sm backdrop-blur order-2 md:order-2"
        >
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold">Company Overview</h2>
            <div className="flex items-center gap-2">
              <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                (info?.status || 'Active') === 'Active' ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200' : 'bg-rose-50 text-rose-700 ring-1 ring-rose-200'
              }`}>
                {info?.status || 'Active'}
              </span>
              <button
                type="button"
                onClick={() => {
                  try { sessionStorage.setItem('scroll_user_dashboard', String(window.scrollY || 0)) } catch {}
                  navigate('/team-management')
                }}
                className="rounded-md bg-gray-100 px-3 py-1.5 text-sm font-medium text-gray-900 ring-1 ring-inset ring-gray-300 hover:bg-gray-200"
              >
                Manage Team Members
              </button>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <div className="text-gray-500">Company</div>
              <div className="font-medium">{info?.company_name || '—'}</div>
            </div>
            <div>
              <div className="text-gray-500">Joined</div>
              <div className="font-medium">{info?.created_at || '—'}</div>
            </div>
            <div>
              <div className="text-gray-500">Plan</div>
              <div className="font-medium">{info?.subscription_plan || '—'}</div>
            </div>
            <div>
              <div className="text-gray-500">Active Users</div>
              <div className="font-medium">{info?.user_count ?? '—'}</div>
            </div>
          </div>
        </motion.div>

        {/* Billing & Subscription (bottom-right on desktop) */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: cards[1].delay }}
          className="rounded-2xl border border-gray-200 bg-white/60 p-6 shadow-sm backdrop-blur order-3 md:order-4"
        >
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold">Billing & Subscription</h2>
            {(() => {
              const myId = me?.user_id
              const myRole = users.find((u) => u.id === myId)?.role
              if (myRole === 'Owner') {
                return (
                  <button
                    disabled
                    className="rounded-md bg-gray-300 px-3 py-1.5 text-sm font-medium text-white opacity-70 cursor-not-allowed"
                    title="Subscription management coming soon"
                  >
                    Manage Subscription
                  </button>
                )
              }
              return null
            })()}
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3 text-sm">
            <div>
              <div className="text-gray-500">Plan</div>
              <div className="font-medium">Starter</div>
            </div>
            <div>
              <div className="text-gray-500">Next Renewal</div>
              <div className="font-medium">N/A</div>
            </div>
            <div>
              <div className="text-gray-500">Billing Email</div>
              <div className="font-medium">{info?.email || me?.email || '—'}</div>
            </div>
          </div>
        </motion.div>

        {/* Company Settings (top-left on desktop) */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: cards[2].delay }}
          className="rounded-2xl border border-gray-200 bg-white/60 p-6 shadow-sm backdrop-blur order-1 md:order-1"
        >
          <h2 className="mb-4 text-lg font-semibold">Company Settings</h2>
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-sm text-gray-600">Company Name</label>
              <input
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-emerald-500 focus:outline-none"
                value={settings.company_name}
                onChange={(e) => setSettings((s) => ({ ...s, company_name: e.target.value }))}
              />
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <div>
                <label className="mb-1 block text-sm text-gray-600">Industry</label>
                <select
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-emerald-500 focus:outline-none"
                  value={settings.industry}
                  onChange={(e) => setSettings((s) => ({ ...s, industry: e.target.value }))}
                >
                  <option value="">Select industry…</option>
                  {INDUSTRIES.map((i) => (
                    <option key={i} value={i}>{i}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm text-gray-600">Timezone</label>
                <select
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-emerald-500 focus:outline-none"
                  value={settings.timezone}
                  onChange={(e) => setSettings((s) => ({ ...s, timezone: e.target.value }))}
                >
                  <option value="">Select timezone…</option>
                  {TIMEZONES.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm text-gray-600">Currency</label>
                <select
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-emerald-500 focus:outline-none"
                  value={settings.currency}
                  onChange={(e) => setSettings((s) => ({ ...s, currency: e.target.value }))}
                >
                  <option value="">Select currency…</option>
                  {CURRENCIES.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <div>
                <label className="mb-1 block text-sm text-gray-600">Address</label>
                <input
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-emerald-500 focus:outline-none"
                  value={settings.address}
                  onChange={(e) => setSettings((s) => ({ ...s, address: e.target.value }))}
                  placeholder="Street, City, State"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm text-gray-600">Phone</label>
                <input
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-emerald-500 focus:outline-none"
                  value={settings.phone}
                  onChange={(e) => setSettings((s) => ({ ...s, phone: e.target.value }))}
                  placeholder="e.g. +1 555 123 4567"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm text-gray-600">Email</label>
                <input
                  type="email"
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-emerald-500 focus:outline-none"
                  value={settings.email}
                  onChange={(e) => setSettings((s) => ({ ...s, email: e.target.value }))}
                  placeholder="billing@company.com"
                />
              </div>
            </div>
            <div className="flex justify-end">
              <button
                disabled={saving}
                onClick={handleSaveSettings}
                className="rounded-md bg-emerald-500 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-emerald-600 disabled:opacity-60"
              >
                {saving ? 'Saving…' : 'Save Changes'}
              </button>
            </div>
          </div>
        </motion.div>

        {/* Security (bottom-left on desktop) */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: cards[3].delay }}
          className="rounded-2xl border border-gray-200 bg-white/60 p-6 shadow-sm backdrop-blur order-4 md:order-3"
        >
          <h2 className="mb-4 text-lg font-semibold">Security</h2>
          <div className="flex flex-wrap gap-3">
            <Link
              to="/settings/security"
              className="rounded-md bg-gray-800 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-gray-900"
            >
              Change Password
            </Link>
            <button
              onClick={() => alert('This will log out all sessions (placeholder).')}
              className="rounded-md bg-gray-100 px-4 py-2 text-sm font-medium text-gray-800 ring-1 ring-inset ring-gray-300 hover:bg-gray-200"
            >
              Logout All Sessions
            </button>
            {(() => {
              const myId = me?.user_id
              const myRole = users.find((u) => u.id === myId)?.role
              if (myRole === 'Owner' || myRole === 'Admin') {
                return (
                  <button
                    type="button"
                    onClick={() => navigate('/audit-log')}
                    className="rounded-md bg-gray-100 px-4 py-2 text-sm font-medium text-gray-800 ring-1 ring-inset ring-gray-300 hover:bg-gray-200"
                  >
                    View Audit Log
                  </button>
                )
              }
              return null
            })()}
          </div>
        </motion.div>
      </div>
    </div>
  )
}
