import { useEffect, useState } from 'react'
import { apiUrl } from '../api'
import type { ChatStatus } from '../chat'

export function useResearchStatus(connected: boolean) {
  const [status, setStatus] = useState<ChatStatus | null>(null)
  const [error, setError] = useState(false)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    if (!connected) return
    let active = true
    let request: AbortController | null = null
    async function check() {
      if (request) return
      const controller = new AbortController()
      request = controller
      // A local hybrid index can initialize slowly. Public no-corpus mode is small.
      const timer = window.setTimeout(() => controller.abort(), 90000)
      try {
        const response = await fetch(apiUrl('/api/chat/status'), { signal: controller.signal, cache: 'no-store' })
        if (!response.ok) throw new Error('Status unavailable')
        const data: ChatStatus = await response.json()
        if (typeof data.available !== 'boolean' || !data.retrieval ||
          !Number.isInteger(data.retrieval.passages) || data.retrieval.passages < 0 ||
          !['available', 'publication_pending', 'unavailable'].includes(data.research_state) ||
          typeof data.research_message !== 'string') throw new Error('Invalid status')
        if (active) { setStatus(data); setError(false) }
      } catch {
        if (active) setError(true)
      } finally {
        window.clearTimeout(timer)
        request = null
      }
    }
    void check()
    const interval = window.setInterval(() => void check(), 15000)
    return () => { active = false; window.clearInterval(interval); request?.abort() }
  }, [connected, attempt])
  return { status, error, retry: () => setAttempt(n => n + 1) }
}
