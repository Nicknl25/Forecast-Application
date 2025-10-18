import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import './styles/tailwind.css'

// Runtime guard: warn if a production Azure base URL sneaks into dev
const runtimeBase = import.meta.env.VITE_API_BASE_URL
if (typeof runtimeBase === 'string' && runtimeBase.includes('azurewebsites.net')) {
  // This helps catch stale prod bundles or misconfigured env at runtime
  console.warn(
    'Warning: API base URL points to an Azure domain in dev:',
    runtimeBase,
    '\nExpected http://localhost:5000 for local development.'
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
)
