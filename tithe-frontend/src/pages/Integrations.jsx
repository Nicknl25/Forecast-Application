export default function Integrations() {
  const providers = [
    { name: 'QuickBooks', description: 'Connect your QuickBooks account to sync data.' },
    { name: 'Xero', description: 'Connect your Xero account to sync data.' },
    { name: 'FreshBooks', description: 'Connect your FreshBooks account to sync data.' },
  ]
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Integrations</h1>
      <div className="grid gap-6 md:grid-cols-3">
        {providers.map((p) => (
          <div key={p.name} className="rounded-lg border bg-white p-6 shadow-sm">
            <h3 className="mb-2 text-lg font-semibold">{p.name}</h3>
            <p className="mb-4 text-gray-600">{p.description}</p>
            <button onClick={() => alert(`${p.name} connect placeholder`)} className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">Connect</button>
          </div>
        ))}
      </div>
    </div>
  )
}

