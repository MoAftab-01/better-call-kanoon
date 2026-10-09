/**
 * Poll `GET /api/health` for the service badge and the knowledge-base indicator.
 *
 * Kept cheap and stopped on error, as required:
 *  - one request immediately, then only while the page is visible;
 *  - never more than once per `intervalMs`;
 *  - the first failure latches the badge to "unavailable" and cancels the
 *    interval, so a dead backend is not hammered from every open tab.
 */
import { useEffect, useRef, useState } from 'react'

import { fetchHealth } from '../api/client'
import type { HealthResponse } from '../types'

export type ServiceState = 'pending' | 'ok' | 'down'

export interface UseHealth {
  state: ServiceState
  health: HealthResponse | null
  /** Re-run a single check immediately, cancelling any back-off. */
  checkNow: () => void
}

const DEFAULT_INTERVAL_MS = 30_000

export function useHealth(intervalMs: number = DEFAULT_INTERVAL_MS): UseHealth {
  const [state, setState] = useState<ServiceState>('pending')
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [attempt, setAttempt] = useState(0)

  const alive = useRef(true)
  const gaveUp = useRef(false)

  useEffect(() => {
    alive.current = true
    gaveUp.current = false
    const controller = new AbortController()

    async function check(): Promise<void> {
      try {
        const data = await fetchHealth({ signal: controller.signal })
        if (!alive.current) return
        setHealth(data)
        setState(data.status === 'healthy' ? 'ok' : 'down')
      } catch {
        if (!alive.current || controller.signal.aborted) return
        // Stop on error: a badge that already says "unavailable" gains nothing
        // from being re-pinged every 30 seconds.
        gaveUp.current = true
        setHealth(null)
        setState('down')
      }
    }

    void check()

    const timer = window.setInterval(() => {
      if (gaveUp.current || document.hidden || controller.signal.aborted) return
      void check()
    }, intervalMs)

    // A tab that has been hidden for minutes should not accumulate a backlog of
    // checks; re-check as soon as the user actually looks at it again.
    function onVisibilityChange(): void {
      if (!document.hidden && !gaveUp.current && !controller.signal.aborted) void check()
    }
    document.addEventListener('visibilitychange', onVisibilityChange)

    return () => {
      alive.current = false
      controller.abort()
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [intervalMs, attempt])

  return { state, health, checkNow: () => setAttempt((value) => value + 1) }
}
