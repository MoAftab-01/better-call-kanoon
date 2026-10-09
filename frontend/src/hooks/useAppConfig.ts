/**
 * Fetch `GET /api/config` once and expose it as loading / error / data.
 *
 * Failure is a supported state, not an exception: with the backend down the app
 * must still render a usable shell with a clear, non-scary notice. Nothing here
 * ever throws and nothing here ever renders a stack trace or a raw error string -
 * `ApiError.message` is copy this project chose, not server output.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchConfig } from '../api/client'
import { FALLBACK_CONFIG, toAppConfig, type AppConfig } from '../api/mappers'

export type ConfigStatus = 'loading' | 'ready' | 'error'

export interface UseAppConfig {
  config: AppConfig
  status: ConfigStatus
  /** `true` once the request has settled either way. */
  settled: boolean
  /** A safe, non-scary message, or `null` when the load succeeded. */
  errorMessage: string | null
  retry: () => void
}

/**
 * Load the public configuration once per mount.
 *
 * A manual `retry()` bumps a nonce, which re-runs the effect. There is no
 * polling here: `/api/health` is the cheap poll and it has its own hook.
 */
export function useAppConfig(): UseAppConfig {
  const [config, setConfig] = useState<AppConfig>(FALLBACK_CONFIG)
  const [status, setStatus] = useState<ConfigStatus>('loading')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  // Guards against a late response landing after unmount or after a newer attempt.
  const active = useRef(true)

  useEffect(() => {
    active.current = true
    const controller = new AbortController()

    setStatus('loading')
    setErrorMessage(null)

    fetchConfig({ signal: controller.signal })
      .then((wire) => {
        if (!active.current) return
        setConfig(toAppConfig(wire))
        setStatus('ready')
      })
      .catch((error: unknown) => {
        if (!active.current || controller.signal.aborted) return
        // The backend being unreachable is an expected condition, not a crash.
        // Stay on the fallback config so the shell keeps working, and keep the
        // message generic - it must name no host, port or path.
        const message =
          error instanceof Error && error.message !== ''
            ? error.message
            : 'The server could not be reached.'
        setErrorMessage(message)
        setStatus('error')
      })

    return () => {
      active.current = false
      controller.abort()
    }
  }, [attempt])

  const retry = useCallback(() => setAttempt((value) => value + 1), [])

  return { config, status, settled: status !== 'loading', errorMessage, retry }
}
