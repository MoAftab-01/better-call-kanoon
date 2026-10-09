/**
 * The single place where the snake_case wire format becomes camelCase for the
 * components.
 *
 * `types.ts` mirrors `backend/app/models.py` exactly, so nothing in here guesses
 * a field name - it only renames. Filtering is still applied where the wire can
 * hand us something unusable: malformed entries are dropped so a schema change
 * shows up as a visibly empty list rather than as a plausible-looking card built
 * from `undefined`. The one filter that cannot be dropped is `mapLanguages`:
 * the server's language list is operator-editable and unvalidated, so a code
 * this build cannot render is removed there rather than crashing the page later.
 *
 * The defaults here mirror the Pydantic defaults in `app/models.py` for the same
 * reason: with the backend down the shell must still render sensibly, and it must
 * do so without inventing legal content. The emergency list is empty by design -
 * no helpline number is ever fabricated locally.
 */
import { isLanguageCode, type LanguageCode } from '../i18n'
import type {
  EmergencyContact,
  PublicConfig,
  StarterQuestion,
  SupportedLanguage,
} from '../types'

/** Fallbacks used only while `/api/config` is loading or after it failed. */
export const FALLBACK_APP_NAME = 'Better Call Kanoon'
export const FALLBACK_TAGLINE = 'Your AI guide to Indian law.'
export const FALLBACK_DESCRIPTION = 'Voice-powered AI legal information grounded in Indian law.'

/**
 * Languages this build can actually render, independent of what the server
 * offers.
 *
 * Typed with a `LanguageCode`, not the wire `string`, so these literals cannot
 * drift out of step with `STRINGS` — a fourth locale here would be a compile
 * error rather than a blank page.
 */
export const BUILT_IN_LANGUAGES: readonly (SupportedLanguage & { code: LanguageCode })[] = [
  {
    code: 'en',
    label: 'English',
    native_label: 'English',
    stt_locale: 'en-IN',
    tts_locale: 'en-IN',
  },
  {
    code: 'hi',
    label: 'Hindi',
    native_label: 'हिन्दी',
    stt_locale: 'hi-IN',
    tts_locale: 'hi-IN',
  },
]

/** Component-facing view of a supported language. */
export interface LanguageOption {
  /**
   * One of the locales this build can render.
   *
   * `LanguageCode`, not `string`: `SUPPORTED_LANGUAGES` is an operator-editable
   * CSV with no allowlist, so a server code outside en/hi is reachable from the
   * wire. Typing it here means `mapLanguages` has to narrow it before it can be
   * handed to the toggle, instead of the component asserting a lie.
   */
  code: LanguageCode
  label: string
  nativeLabel: string
  sttLocale: string
  ttsLocale: string
}

/** Component-facing view of an emergency contact. */
export interface ContactCard {
  id: string
  label: string
  number: string
  note: string
  source: string
  verified: boolean
  /** `tel:` href, or `null` when the number has no dialable characters. */
  dialHref: string | null
}

/** Component-facing view of `GET /api/config`. */
export interface AppConfig {
  appName: string
  tagline: string
  description: string
  languages: LanguageOption[]
  defaultLanguage: string
  llmConfigured: boolean
  knowledgeBaseReady: boolean
  /** `0` means "no limit advertised"; the composer then imposes none. */
  maxInputLength: number
  speechRates: number[]
  /**
   * Starter questions, filtered to those with usable text but otherwise
   * unchanged. `text_en` / `text_hi` are kept as-is because which one is read
   * depends on the active language at render time, not at map time.
   */
  starterCards: StarterQuestion[]
  disclaimer: string
  contacts: ContactCard[]
}

/** Keep only non-negative finite integers; anything else means "no limit". */
function readLimit(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) && value > 0
    ? Math.floor(value)
    : 0
}

/**
 * Build the language picker options.
 *
 * Drops any code this build cannot render. `SUPPORTED_LANGUAGES` is a free-form
 * CSV (`_parse_str_list` is a bare split, and `main.py` fabricates a
 * label/locale for unknown codes), so the server will happily advertise one.
 * Offering it in the toggle would let a click commit a language with no entry
 * in `STRINGS`, and the render that follows would throw on `strings.x` — with no
 * error boundary above it. Filtering here is the same rule
 * `mapStarterQuestions` and `mapContacts` already apply to unusable entries.
 *
 * Falls back to the built-in locales when nothing renderable survives (or the
 * server has not answered), so the toggle is never an empty group.
 */
function mapLanguages(raw: PublicConfig['supported_languages']): LanguageOption[] {
  if (!Array.isArray(raw) || raw.length === 0) {
    return BUILT_IN_LANGUAGES.map((item) => toLanguageOption(item, item.code))
  }
  const renderable = raw
    .filter(
      (item): item is SupportedLanguage & { code: LanguageCode } =>
        typeof item?.code === 'string' && isLanguageCode(item.code),
    )
    .map((item) => toLanguageOption(item, item.code))
  return renderable.length > 0
    ? renderable
    : BUILT_IN_LANGUAGES.map((item) => toLanguageOption(item, item.code))
}

/**
 * Build one picker option from a wire record.
 *
 * Takes the code as an argument rather than reading `item.code` so the
 * narrowing done by `mapLanguages` has to be passed in explicitly - there is no
 * path from a raw `SupportedLanguage` to a `LanguageOption` that skips the
 * renderability check.
 */
function toLanguageOption(item: SupportedLanguage, code: LanguageCode): LanguageOption {
  return {
    code,
    label: item.label || code,
    nativeLabel: item.native_label || item.label || code,
    sttLocale: item.stt_locale || code,
    ttsLocale: item.tts_locale || code,
  }
}

/**
 * Map starter questions to cards.
 *
 * Each entry keeps only its id and the two wire field names; which one is read
 * depends on the active language at render time. A card with no usable text in
 * either language is dropped rather than rendered blank.
 */
function mapStarterQuestions(raw: PublicConfig['starter_questions']): StarterQuestion[] {
  if (!Array.isArray(raw)) return []
  return raw.filter(
    (item: StarterQuestion | undefined | null): item is StarterQuestion =>
      typeof item?.id === 'string' &&
      typeof item.text_en === 'string' &&
      typeof item.text_hi === 'string' &&
      (item.text_en.trim() !== '' || item.text_hi.trim() !== ''),
  )
}

/** Keep only records with a dialable number; a blank card helps nobody. */
function mapContacts(raw: PublicConfig['emergency_contacts']): ContactCard[] {
  if (!Array.isArray(raw)) return []
  return raw
    .filter(
      (item: EmergencyContact | undefined | null): item is EmergencyContact =>
        typeof item?.number === 'string' && item.number.trim() !== '',
    )
    .map((item) => ({
      id: item.id,
      label: item.label || item.number,
      number: item.number,
      note: typeof item.note === 'string' ? item.note : '',
      source: typeof item.source === 'string' ? item.source : '',
      verified: item.verified === true,
      dialHref: buildDialHref(item.number),
    }))
}

/**
 * Build a `tel:` href, or `null` when nothing survives sanitising.
 *
 * Strips every character that is not a digit or a leading `+`, matching the
 * vanilla frontend. A `tel:` link is handed to the OS dial handler, so the
 * value must never be able to carry a scheme or extra parameters.
 */
export function buildDialHref(number: string): string | null {
  const sanitised = number.replace(/[^\d+]/g, '')
  const hasDigit = /\d/.test(sanitised)
  return hasDigit ? `tel:${sanitised}` : null
}

/**
 * Turn the wire config into the view model components consume.
 *
 * This is the *only* boundary mapping. Everything upstream is the backend's
 * shape; everything downstream is ours.
 */
export function toAppConfig(config: PublicConfig): AppConfig {
  const speechRates = Array.isArray(config.speech_rates)
    ? config.speech_rates.filter(
        (rate): rate is number => typeof rate === 'number' && Number.isFinite(rate) && rate > 0,
      )
    : []

  return {
    appName: config.app_name || FALLBACK_APP_NAME,
    tagline: config.tagline || FALLBACK_TAGLINE,
    description: config.description || FALLBACK_DESCRIPTION,
    languages: mapLanguages(config.supported_languages),
    defaultLanguage:
      typeof config.default_language === 'string' && config.default_language !== ''
        ? config.default_language
        : 'en',
    llmConfigured: config.llm_configured === true,
    knowledgeBaseReady: config.knowledge_base_ready === true,
    maxInputLength: readLimit(config.max_input_length),
    speechRates,
    starterCards: mapStarterQuestions(config.starter_questions),
    disclaimer: typeof config.disclaimer === 'string' ? config.disclaimer : '',
    contacts: mapContacts(config.emergency_contacts),
  }
}

/**
 * The config used before the first successful fetch, and after a failed one.
 *
 * No emergency contacts and no starter questions: those are legal/system data
 * and must come from the backend or not appear at all.
 */
export const FALLBACK_CONFIG: AppConfig = {
  appName: FALLBACK_APP_NAME,
  tagline: FALLBACK_TAGLINE,
  description: FALLBACK_DESCRIPTION,
  languages: BUILT_IN_LANGUAGES.map((item) => toLanguageOption(item, item.code)),
  defaultLanguage: 'en',
  llmConfigured: false,
  knowledgeBaseReady: false,
  maxInputLength: 0,
  speechRates: [],
  starterCards: [],
  disclaimer: '',
  contacts: [],
}
