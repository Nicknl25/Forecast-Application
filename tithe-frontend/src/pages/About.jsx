import { motion } from 'framer-motion'

export default function About() {
  return (
    <div className="space-y-10">
      <header>
        <h1 className="text-3xl font-bold">About Us</h1>
        <p className="mt-2 text-gray-600">Our story, mission, and values.</p>
      </header>
      <motion.section initial={{ opacity: 0, y: 12 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
        <div className="rounded-lg border bg-white p-6 shadow-sm">
          <h3 className="mb-2 text-lg font-semibold">Our Mission</h3>
          <p className="text-gray-700">We empower finance teams with clear, actionable analytics. Tithe Financial is built for modern workflows, security, and scale.</p>
        </div>
      </motion.section>
      <motion.section initial={{ opacity: 0, y: 12 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
        <div className="rounded-lg border bg-white p-6 shadow-sm">
          <h3 className="mb-2 text-lg font-semibold">Credibility</h3>
          <ul className="list-disc space-y-2 pl-5 text-gray-700">
            <li>Backed by industry experts</li>
            <li>Secure-by-default architecture</li>
            <li>Deployed on Azure infrastructure</li>
          </ul>
        </div>
      </motion.section>
    </div>
  )
}

