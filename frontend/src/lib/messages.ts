/**
 * The conversation model.
 *
 * Stage 1 has no answering endpoint, so nothing here fabricates a reply. The one
 * message the app can produce on its own is an honest "this is not available yet"
 * notice - which is exactly the point: a plausible-looking invented legal answer
 * would be far worse than no answer at all.
 */
import type { LanguageCode } from '../hooks/useLanguage'

export type MessageRole = 'user' | 'app'

export interface Message {
  id: string
  role: MessageRole
  text: string
  /** BCP-47 tag the text is written in, so a screen reader voices it correctly. */
  lang: LanguageCode
  /** `true` for the "arrives in a later stage" notice. */
  isNotice?: boolean
}

let counter = 0

/**
 * Monotonic ids.
 *
 * Deliberately not `crypto.randomUUID()`: nothing here is persisted or sent
 * anywhere, and a counter keeps the bundle free of a polyfill assumption.
 */
export function nextMessageId(prefix: string): string {
  counter += 1
  return `${prefix}-${counter}`
}

/** Reset the counter. Only useful for tests and hot reloads. */
export function resetMessageIds(): void {
  counter = 0
}
