/**
 * Localised copy for a starter question.
 *
 * Lives outside `components/StarterQuestions.tsx` so that file exports only
 * components: a module that mixes a component with a plain helper defeats Vite's
 * fast-refresh boundary check and makes every edit a full reload.
 *
 * The fallback matters. The wire carries `text_en` and `text_hi` for every
 * record, but a partially-translated backend should degrade to the other
 * language rather than render a blank card.
 */
import type { LanguageCode } from '../i18n'
import type { StarterQuestion } from '../types'

/**
 * Pick the copy for one question in the active language.
 *
 * Returns `''` when neither locale has text, which is the caller's signal to
 * skip the card entirely.
 */
export function localisedStarterText(
  question: StarterQuestion,
  language: LanguageCode,
): string {
  const preferred = language === 'hi' ? question.text_hi : question.text_en
  const fallback = language === 'hi' ? question.text_en : question.text_hi
  return preferred || fallback || ''
}