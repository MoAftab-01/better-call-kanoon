/**
 * The empty-state starter questions.
 *
 * Each card carries `text_en` and `text_hi` on the wire, so the active language
 * picks the field at render time. Clicking a card fills the composer and states
 * plainly that answering is not available yet — a card must never look like it
 * produced an answer.
 */
import type { LanguageCode } from '../hooks/useLanguage'
import type { Strings } from '../i18n'
import { localisedStarterText } from '../lib/starterQuestions'
import type { StarterQuestion } from '../types'

interface StarterQuestionsProps {
  /** `PublicConfig.starter_questions`, unchanged. */
  questions: StarterQuestion[]
  language: LanguageCode
  strings: Strings
  onSelect: (text: string) => void
}

export function StarterQuestions({
  questions,
  language,
  strings,
  onSelect,
}: StarterQuestionsProps) {
  if (!Array.isArray(questions) || questions.length === 0) return null

  return (
    <section className="starter" aria-labelledby="starter-heading">
      <h2 className="section-heading" id="starter-heading">
        {strings.sectionStarter}
      </h2>
      <ul className="starter-grid">
        {questions.map((question) => {
          const text = localisedStarterText(question, language)
          if (text.trim() === '') return null
          return (
            <li key={question.id}>
              <button
                type="button"
                className="starter-card"
                lang={language}
                onClick={() => onSelect(text)}
              >
                {text}
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
