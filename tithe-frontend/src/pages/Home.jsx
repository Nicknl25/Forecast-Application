import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'

export default function Home() {
  return (
    <div className="space-y-16">
      <section className="relative overflow-hidden rounded-xl bg-gradient-to-br from-blue-50 to-emerald-50 p-10">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
          <h1 className="text-4xl font-bold tracking-tight text-gray-900 md:text-5xl">
            Smarter Analytics for Finance Teams
          </h1>
          <p className="mt-4 max-w-2xl text-gray-600">
            Tithe Financial helps you connect accounting data and unlock insights across your organization.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link to="/integrations" className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">Connect QuickBooks</Link>
            <Link to="/dashboard" className="rounded-md bg-gray-100 px-4 py-2 text-sm font-medium text-gray-900 hover:bg-gray-200">See Demo</Link>
            <Link to="/signup" className="rounded-md bg-emerald-500 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-600">Start Free Trial</Link>
          </div>
        </motion.div>
        <motion.div
          className="pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full bg-blue-200/50 blur-3xl"
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.2, duration: 0.8 }}
        />
      </section>

      <section className="grid gap-6 md:grid-cols-3">
        {[
          { title: 'Connect Data', text: 'Sync QuickBooks, Xero, and more.' },
          { title: 'Visualize Metrics', text: 'Dashboards and charts built for speed.' },
          { title: 'Share Insights', text: 'Collaborate across teams securely.' },
        ].map((item) => (
          <motion.div key={item.title} initial={{ opacity: 0, y: 12 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.4 }}>
            <div className="rounded-lg border bg-white p-6 shadow-sm">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-lg font-semibold">{item.title}</h3>
              </div>
              <p className="text-gray-600">{item.text}</p>
            </div>
          </motion.div>
        ))}
      </section>
    </div>
  )
}

