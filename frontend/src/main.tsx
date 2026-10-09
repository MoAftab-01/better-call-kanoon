/**
 * React entry point.
 *
 * Kept deliberately thin: `index.html` loads only this file, and everything
 * that owns state lives in `App`. The stylesheet is imported here so Vite emits
 * it as a bundled asset — there is no separate `<link>` to a CDN or a remote
 * font, which is what keeps the app at zero network egress beyond its own
 * backend.
 *
 * `StrictMode` is on: it double-invokes effects in development, which is exactly
 * what caught the speech-engine teardown and the late-resolving language
 * preference during development.
 */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './App'
import './index.css'

const container = document.getElementById('root')
if (!container) {
  // Only reachable if `index.html` and this file disagree. Fail loudly in the
  // console rather than rendering nothing with no explanation.
  throw new Error('Root element #root was not found in index.html.')
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
)