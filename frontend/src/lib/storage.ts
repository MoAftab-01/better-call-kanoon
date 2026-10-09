/**
 * Guarded `localStorage` / `sessionStorage` access.
 *
 * Private-mode browsers and hardened profiles throw on any storage access, so
 * every call here is wrapped. A storage failure must never take the page down:
 * a preference simply is not remembered, which is an acceptable degradation for
 * a read-aloud toggle or a dismissed banner.
 */
export const STORAGE_KEYS = {
  language: 'bck_language',
  speechRate: 'bck_speech_rate',
  readAloud: 'bck_read_aloud',
  disclaimerDismissed: 'bck_disclaimer_dismissed',
} as const

/** Read a string, or `null` when absent or when storage is unavailable. */
export function readLocal(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

export function writeLocal(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value)
  } catch {
    // Storage unavailable. The in-memory state still applies for this session.
  }
}

/** Read a session-scoped string. Used for the disclaimer, which resets per visit. */
export function readSession(key: string): string | null {
  try {
    return window.sessionStorage.getItem(key)
  } catch {
    return null
  }
}

export function writeSession(key: string, value: string): void {
  try {
    window.sessionStorage.setItem(key, value)
  } catch {
    // As above.
  }
}
