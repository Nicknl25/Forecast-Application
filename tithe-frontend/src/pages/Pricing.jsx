import { motion } from 'framer-motion'

const tiers = [
  { name: 'Basic', price: '$19/mo', features: ['Up to 2 integrations', 'Basic dashboards', 'Email support'] },
  { name: 'Pro', price: '$49/mo', features: ['Up to 5 integrations', 'Advanced dashboards', 'Priority support'] },
  { name: 'Enterprise', price: 'Contact us', features: ['Unlimited integrations', 'Custom SLAs', 'Dedicated success'] },
]

export default function Pricing() {
  return (
    <div className="space-y-10">
      <header>
        <h1 className="text-3xl font-bold">Pricing</h1>
        <p className="mt-2 text-gray-600">Choose the plan that fits your needs.</p>
      </header>
      <div className="grid gap-6 md:grid-cols-3">
        {tiers.map((tier, idx) => (
          <motion.div key={tier.name} initial={{ opacity: 0, y: 12 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.4, delay: idx * 0.1 }}>
            <div className="h-full rounded-lg border bg-white p-6 shadow-sm">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-lg font-semibold">{tier.name}</h3>
              </div>
              <p className="mb-4 text-2xl font-semibold">{tier.price}</p>
              <ul className="mb-6 space-y-2 text-sm text-gray-600">
                {tier.features.map((f) => (
                  <li key={f}>• {f}</li>
                ))}
              </ul>
              <button onClick={() => alert('PayPal checkout placeholder')} className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">Pay with PayPal</button>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}

