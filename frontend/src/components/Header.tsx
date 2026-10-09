/**
 * Sticky site header: wordmark, tagline, language toggle, emergency button and
 * the service-health badge.
 *
 * Built from the original vanilla-JS prototype's `<header class="site-header">`
 * with the same class names, so the rendered markup matches that layout.
 */
import type { LanguageOption } from '../api/mappers'
import type { ServiceState } from '../hooks/useHealth'
import type { LanguageCode } from '../hooks/useLanguage'
import type { Strings } from '../i18n'
import { LanguageToggle } from './LanguageToggle'

interface HeaderProps {
  appName: string
  tagline: string
  languages: LanguageOption[]
  language: LanguageCode
  onLanguageChange: (code: LanguageCode) => void
  serviceState: ServiceState
  strings: Strings
  emergencyOpen: boolean
  onEmergencyOpen: () => void
}

/** The scales-of-justice mark from the original header, inlined as SVG. */
function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <svg viewBox="0 0 32 32" focusable="false">
        <path d="M9 7v11a7 7 0 0 0 14 0V7" />
        <path d="M7 26h18" />
      </svg>
    </span>
  )
}

export function Header({
  appName,
  tagline,
  languages,
  language,
  onLanguageChange,
  serviceState,
  strings,
  emergencyOpen,
  onEmergencyOpen,
}: HeaderProps) {
  const statusText =
    serviceState === 'ok'
      ? strings.statusHealthy
      : serviceState === 'down'
        ? strings.statusDown
        : strings.statusChecking

  return (
    <header className="site-header">
      <div className="shell header-inner">
        <div className="brand">
          <BrandMark />
          <span className="brand-text">
            {/* Uppercase is a CSS `text-transform`, so screen readers announce
                "Better Call Kanoon" rather than spelling it out. */}
            <span className="brand-name">{appName}</span>
            <span className="brand-tagline">{tagline}</span>
          </span>
        </div>

        <div className="header-actions">
          <LanguageToggle
            languages={languages}
            language={language}
            onChange={onLanguageChange}
            label={strings.languageGroup}
          />
          <button
            type="button"
            className="btn btn-emergency"
            onClick={onEmergencyOpen}
            aria-haspopup="dialog"
            aria-expanded={emergencyOpen}
            aria-controls="emergency-panel"
          >
            <span className="dot dot-alert" aria-hidden="true" />
            {strings.emergencyBtn}
          </button>
          {/* `role="status"` + polite live region: the badge updates without
              interrupting whatever the user is doing. */}
          <p className="service-status" role="status" aria-live="polite">
            <span className="dot" data-state={serviceState} aria-hidden="true" />
            <span>{statusText}</span>
          </p>
        </div>
      </div>
    </header>
  )
}
