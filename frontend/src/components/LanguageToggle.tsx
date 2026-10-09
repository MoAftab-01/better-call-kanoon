/**
 * The EN / हिन्दी toggle.
 *
 * A `role="group"` of `aria-pressed` toggle buttons rather than a `<select>`:
 * with exactly two options, visible buttons are faster to hit and work with a
 * screen reader's landmark navigation. `lang` on each button makes assistive
 * technology switch voice to that language.
 */
import type { LanguageOption } from '../api/mappers'
import type { LanguageCode } from '../hooks/useLanguage'

interface LanguageToggleProps {
  languages: LanguageOption[]
  language: LanguageCode
  onChange: (code: LanguageCode) => void
  label: string
}

export function LanguageToggle({ languages, language, onChange, label }: LanguageToggleProps) {
  return (
    <div className="lang-switch" role="group" aria-label={label}>
      {languages.map((option) => (
        <button
          key={option.code}
          type="button"
          className="lang-btn"
          lang={option.code}
          aria-label={option.label}
          aria-pressed={option.code === language}
          onClick={() => onChange(option.code)}
        >
          {option.nativeLabel}
        </button>
      ))}
    </div>
  )
}
