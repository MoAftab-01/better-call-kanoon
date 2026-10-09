/**
 * Typed `fetch` helpers for the two public backend routes.
 *
 * Contract (see `backend/app/main.py` and `backend/app/api/health.py`):
 *   GET /api/health -> HealthResponse
 *   GET /api/config -> PublicConfig
 *
 * Both are public GETs returning snake_case JSON.
 *
 * Security rule that shapes this whole file: an `ApiError` carries only a
 * status code and a message this file chooses itself. The server's response body
 * is never surfaced to the browser, and neither is the underlying `Error` text -
 * which for a failed fetch would otherwise be a string like
 * "Failed to fetch" that tells a user nothing and tells an attacker where the
 * service lives. No traceback, filesystem path or `site-packages` string can
 * reach the UI from here.
 */
import type { HealthResponse, PublicConfig } from '../types'

const CONFIG_ENDPOINT = '/api/config'
const HEALTH_ENDPOINT = '/api/health'

/**
 * An API call that did not succeed.
 *
 * `status` is `0` when the request never reached the server (offline, DNS
 * failure, connection refused). `code` is the backend's machine-readable slug
 * when it sent one, and `null` otherwise.
 */
export class ApiError extends Error {
  readonly status: number
  readonly code: string | null
  /** `true` when the request never reached the server. */
  readonly offline: boolean

  constructor(message: string, options: { status?: number; code?: string | null } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = options.status ?? 0
    this.code = options.code ?? null
    this.offline = this.status === 0
  }
}

/** Human-safe, non-scary messages. Never an exception message, never a stack. */
const MESSAGES: Record<number, string> = {
  0: 'The server could not be reached.',
  404: 'That endpoint is not available.',
  405: 'That request method is not supported.',
  500: 'Something went wrong while processing the request.',
  503: 'The service is temporarily unavailable.',
}

/** Requests are abandoned after this long so the UI never hangs on a dead socket. */
const REQUEST_TIMEOUT_MS = 10_000

interface GetOptions {
  signal?: AbortSignal
}

/**
 * Read the backend's `{"error": slug, "message": text}` envelope, if present.
 *
 * The message is deliberately discarded: the backend's copy is written for
 * browsers, but reusing it verbatim would couple the UI wording to a server-side
 * string. Only the slug - a closed vocabulary of fixed slugs, never free text -
 * is kept, and even that is length-capped and pattern-checked below.
 */
function readErrorEnvelope(body: unknown): string | null {
  if (typeof body !== 'object' || body === null) return null
  const code = (body as { error?: unknown }).error
  if (typeof code !== 'string') return null
  // A slug is lowercase snake_case. Anything else is not one of ours.
  return /^[a-z][a-z0-9_]{0,39}$/.test(code) ? code : null
}

/**
 * Perform a GET against the backend and parse a JSON body.
 *
 * @throws {ApiError} on any non-2xx response, on a transport failure, or when
 * the body is not JSON. Never throws the raw `fetch` rejection reason.
 */
async function getJson<T>(url: string, options: GetOptions = {}): Promise<T> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  // Honour a caller-supplied signal alongside our own timeout.
  const onExternalAbort = () => controller.abort()
  options.signal?.addEventListener('abort', onExternalAbort)

  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal: controller.signal,
      // Same-origin in both dev (Vite proxy) and production (FastAPI mount).
      credentials: 'same-origin',
      cache: 'no-store',
    })

    if (!response.ok) {
      throw new ApiError(MESSAGES[response.status] ?? 'The request failed.', {
        status: response.status,
        code: await readEnvelopeCode(response),
      })
    }

    try {
      return (await response.json()) as T
    } catch {
      throw new ApiError('The server sent a response this page could not read.', {
        status: response.status,
      })
    }
  } catch (error) {
    // An abort is either our timeout or the caller cancelling. Both are benign,
    // and neither is worth surfacing as a failure.
    if (error instanceof ApiError) throw error
    if (controller.signal.aborted) {
      throw new ApiError('The request timed out.', { status: 0 })
    }
    throw new ApiError(MESSAGES[0]!, { status: 0 })
  } finally {
    clearTimeout(timeout)
    options.signal?.removeEventListener('abort', onExternalAbort)
  }
}

/** Pull the slug out of an error body without ever letting it reach the caller as text. */
async function readEnvelopeCode(response: Response): Promise<string | null> {
  try {
    const body: unknown = await response.json()
    return readErrorEnvelope(body)
  } catch {
    // Not JSON - a proxy error page, most likely. There is no code to read.
    return null
  }
}

/**
 * Fetch the browser-safe public configuration.
 *
 * Re-read on every call, so emergency contacts can change without a restart.
 */
export function fetchConfig(options?: GetOptions): Promise<PublicConfig> {
  return getJson<PublicConfig>(CONFIG_ENDPOINT, options)
}

/** Fetch service health, including the retrieval-index status. */
export function fetchHealth(options?: GetOptions): Promise<HealthResponse> {
  return getJson<HealthResponse>(HEALTH_ENDPOINT, options)
}
