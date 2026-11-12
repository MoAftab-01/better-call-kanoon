import { useEffect, useState } from 'react'
import { apiUrl } from '../api'

type ConnectionState = 'checking' | 'connected' | 'disconnected'

export interface BackendConnection {
  state: ConnectionState
  detail: string
}

const checking: BackendConnection = {
  state: 'checking',
  detail: 'Checking the connection to the backend.',
}

export function useBackendHealth() {
  const [connection, setConnection] = useState<BackendConnection>(checking)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let active = true
    let currentRequest: AbortController | undefined

    async function checkHealth() {
      currentRequest?.abort()
      const controller = new AbortController()
      currentRequest = controller
      const timeout = window.setTimeout(() => controller.abort(), 5000)

      try {
        const response = await fetch(apiUrl('/api/health'), {
          signal: controller.signal,
          cache: 'no-store',
          headers: { Accept: 'application/json' },
        })
        if (!response.ok) throw new Error('The backend returned an error.')

        const data: unknown = await response.json()
        if (
          typeof data !== 'object' ||
          data === null ||
          !('status' in data) ||
          data.status !== 'healthy' ||
          !('service' in data) ||
          data.service !== 'better-call-kanoon'
        ) {
          throw new Error('The backend returned an unexpected health response.')
        }

        if (active && currentRequest === controller) {
          setConnection({
            state: 'connected',
            detail: 'The Better Call Kanoon backend is healthy. Chat checks evidence and provider availability separately.',
          })
        }
      } catch {
        if (active && currentRequest === controller) {
          setConnection({
            state: 'disconnected',
            detail: controller.signal.aborted
              ? 'The backend may be starting or unavailable. It did not respond within 5 seconds; checks retry automatically.'
              : 'The backend is unavailable or returned an unexpected response. You can retry the connection.',
          })
        }
      } finally {
        window.clearTimeout(timeout)
      }
    }

    void checkHealth()
    const interval = window.setInterval(() => void checkHealth(), 15000)

    return () => {
      active = false
      window.clearInterval(interval)
      currentRequest?.abort()
    }
  }, [attempt])

  function retry() {
    setConnection(checking)
    setAttempt((previous) => previous + 1)
  }

  return { connection, retry }
}
