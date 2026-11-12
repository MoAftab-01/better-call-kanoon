/** Hosting build gate. Values are never printed; no network request is made. */
let valid = false
try {
  const value = process.env.VITE_API_BASE_URL || ''
  const url = new URL(value)
  valid = url.protocol === 'https:' && !!url.hostname && !url.username && !url.password &&
    url.pathname === '/' && !url.search && !url.hash
} catch { /* Report only the variable name, never its potentially sensitive value. */ }
if (!valid) {
  console.error('Set VITE_API_BASE_URL to the backend HTTPS origin, without credentials, path, query or fragment.')
  process.exitCode = 1
} else console.log('Hosted API origin configuration is valid. No secrets belong in VITE_* variables.')
