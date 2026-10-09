/**
 * TypeScript interfaces mirroring `backend/app/models.py` exactly.
 *
 * The backend emits snake_case JSON (`text_en`, `stt_locale`, `knowledge_base`),
 * so the wire types here are snake_case too. Nothing at this boundary is
 * "prettified" into camelCase - renaming happens once, in `src/api/mappers.ts`,
 * and only where it makes a component easier to read. Keep it that way: the
 * moment field names are guessed rather than verified against the Pydantic
 * models, the UI silently renders `undefined`.
 *
 * Disclaimer: this project provides general legal INFORMATION. It is not a
 * lawyer and does not provide legal advice.
 */

/** `GET /api/health` -> `HealthResponse.knowledge_base` */
export interface KnowledgeBaseStatus {
  /** True when a built index is on disk. */
  ready: boolean
  /** Indexed law chunks, or 0 when not built. */
  chunks: number
  /** Origin of the knowledge base. */
  source: string
}

/** `GET /api/health` -> `HealthResponse` */
export interface HealthResponse {
  /** Exactly 'healthy' while the service is up. */
  status: string
  service: string
  version: string
  /** 'local' in debug mode, otherwise 'production'. */
  environment: string
  knowledge_base: KnowledgeBaseStatus
}

/** `GET /api/config` -> `PublicConfig.supported_languages[]` */
export interface SupportedLanguage {
  /** ISO-style language code. */
  code: string
  /** English name. */
  label: string
  /** Name written in that language. */
  native_label: string
  /** Speech-recognition locale. */
  stt_locale: string
  /** Speech-synthesis locale. */
  tts_locale: string
}

/** `GET /api/config` -> `PublicConfig.starter_questions[]` */
export interface StarterQuestion {
  /** Stable identifier. */
  id: string
  /** English text. */
  text_en: string
  /** Hindi text. */
  text_hi: string
}

/** `GET /api/config` -> `PublicConfig.emergency_contacts[]` */
export interface EmergencyContact {
  /** Stable identifier. */
  id: string
  label: string
  /** Dialable number. */
  number: string
  /** When to use this number. */
  note: string
  /** Official programme behind it. */
  source: string
  /**
   * Checked against an official source. Every record currently ships as
   * `false`, and the UI must show that honestly rather than implying the
   * numbers are authoritative.
   */
  verified: boolean
}

/** `GET /api/config` -> `PublicConfig` */
export interface PublicConfig {
  app_name: string
  tagline: string
  description: string
  supported_languages: SupportedLanguage[]
  /** Language selected on first load. */
  default_language: string
  /** Whether the server has an LLM API key. A boolean only - never the key. */
  llm_configured: boolean
  /** Whether the retrieval index is built. */
  knowledge_base_ready: boolean
  /** Maximum accepted length of a user question. */
  max_input_length: number
  /** Playback rate multipliers for the speech controls. */
  speech_rates: number[]
  starter_questions: StarterQuestion[]
  disclaimer: string
  emergency_contacts: EmergencyContact[]
}

/**
 * The subset of `PublicConfig` needed before the first successful fetch, so the
 * shell is usable while the request is in flight or after it fails.
 *
 * Field names match `PublicConfig` exactly, which is what makes the cast in
 * `src/api/mappers.ts` sound. The emergency list is deliberately empty: no
 * helpline number is ever invented locally.
 */
export type PartialConfig = Pick<PublicConfig, 'app_name'> & Partial<PublicConfig>
