/** Public backend origin only. Never put credentials in VITE_* variables. */
const configured = import.meta.env.VITE_API_BASE_URL || ''
let origin = ''
if (configured) {
  const parsed = new URL(configured)
  if (parsed.protocol !== 'https:' || parsed.username || parsed.password || parsed.search || parsed.hash || parsed.pathname !== '/') {
    throw new Error('VITE_API_BASE_URL must be an HTTPS origin without a path or credentials.')
  }
  origin = parsed.origin
}
export function apiUrl(path: string) { return origin + path }
