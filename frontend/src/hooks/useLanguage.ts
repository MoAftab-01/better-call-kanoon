/**
 * Language selection (EN / HI) with `localStorage` persistence.
 *
 * Built from the original vanilla-JS prototype, including its precedence
 * order:
 *
 *   1. a stored preference the user made here before;
 *   2. otherwise the backend's `default_language` - the server's configured
 *      default wins over the browser's guess, so the selected language is never
 *      hardcoded in the frontend;
 *   3. otherwise the browser's own locale.
 *
 * The stored value is scoped per language, not just per visit: a user who picks
 * Hindi once keeps it next time.
 */
import { useCallback, useEffect, useState } from 'react'

import { isLanguageCode, STRINGS, type LanguageCode } from '../i18n'

export type { LanguageCode }

const STORAGE_KEY = 'bck_language'
const FALLBACK: LanguageCode = 'en'

/**
 * Private-mode browsers throw on any storage access, so every read and write is
 * guarded. A failed read must not take the page down with it.
 */
function readStoredLanguage(): LanguageCode | null {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    return isLanguageCode(saved) ? saved : null
  } catch {
    return null
  }
}

function writeStoredLanguage(code: LanguageCode): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, code)
  } catch {
    // Storage is unavailable (private mode, disabled cookies). The choice still
    // applies for this session; it simply will not be remembered.
  }
}

/** `navigator.language` is a BCP-47 tag, so match on the primary subtag. */
function detectBrowserLanguage(): LanguageCode {
  const tag = (navigator.language || '').toLowerCase()
  return tag.startsWith('hi') ? 'hi' : FALLBACK
}

/**
 * Pick the initial language.
 *
 * @param serverDefault `PublicConfig.default_language`, once known. Before the
 * config arrives this is `null` and only the stored preference or the browser
 * locale can win.
 */
export function resolveInitialLanguage(serverDefault: string | null): LanguageCode {
  const stored = readStoredLanguage()
  if (stored) return stored
  if (serverDefault !== null && isLanguageCode(serverDefault)) return serverDefault
  return detectBrowserLanguage()
}

export interface UseLanguage {
  language: LanguageCode
  setLanguage: (code: LanguageCode) => void
  strings: (typeof STRINGS)[LanguageCode]
}

/**
 * Hold the active language and keep `<html lang>` in sync.
 *
 * The `defaultLanguage` argument only matters on the first render, so the
 * effect below deliberately does not list it as a dependency: changing the
 * server default later must not silently override a choice the user already made.
 */
export function useLanguage(defaultLanguage: string | null): UseLanguage {
  const [language, setLanguageState] = useState<LanguageCode>(() =>
    resolveInitialLanguage(defaultLanguage),
  )

  // Applied after mount as well as on change: the server default is not known on
  // the first render, so a first-time visitor without a stored preference is
  // resolved once the config lands.
  const [resolved, setResolved] = useState(false)
  useEffect(() => {
    if (resolved || defaultLanguage === null) return
    const next = resolveInitialLanguage(defaultLanguage)
    setLanguageState(next)
    setResolved(true)
  }, [defaultLanguage, resolved])

  useEffect(() => {
    document.documentElement.lang = STRINGS[language].htmlLang
  }, [language])

  const setLanguage = useCallback((code: LanguageCode) => {
    setLanguageState((current: LanguageCode) => {
      if (code === current) return current
      // Defence in depth. `LanguageCode` already forbids an unrenderable code at
      // compile time, but the value originates in the server's
      // `supported_languages` list, and a caller that widens it would otherwise
      // commit a code with no `STRINGS` table. Rejecting it here keeps the
      // current language instead of letting a render throw on `strings.x`.
      if (!isLanguageCode(code)) return current
      writeStoredLanguage(code)
      return code
    })
  }, [])

  return { language, setLanguage, strings: STRINGS[language] }
}
