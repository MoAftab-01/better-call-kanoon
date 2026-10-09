/**
 * The legal-information disclaimer.
 *
 * The text comes from `PublicConfig.disclaimer`, never from a local copy, so it
 * is always the wording the backend is actually serving. Dismissal is
 * session-scoped: it disappears on reload rather than being buried permanently,
 * because this is the single most important sentence in the product.
 */
import { useCallback, useEffect, useState } from 'react'

import type { Strings } from '../i18n'
import { readSession, STORAGE_KEYS, writeSession } from '../lib/storage'

interface DisclaimerBannerProps {
  /** `PublicConfig.disclaimer`. Empty until the config loads. */
  text: string
  strings: Strings
}

export function DisclaimerBanner({ text, strings }: DisclaimerBannerProps) {
  const [dismissed, setDismissed] = useState(false)

  // Read once on mount: a dismissal earlier in this same tab session counts.
  useEffect(() => {
    setDismissed(readSession(STORAGE_KEYS.disclaimerDismissed) === '1')
  }, [])

  const dismiss = useCallback(() => {
    setDismissed(true)
    writeSession(STORAGE_KEYS.disclaimerDismissed, '1')
  }, [])

  // Nothing to show until the real disclaimer has arrived, or after dismissal.
  if (dismissed || text.trim() === '') return null

  return (
    <div className="banner" role="note">
      <p className="banner-text">{text}</p>
      <button
        type="button"
        className="banner-close"
        onClick={dismiss}
        aria-label={strings.dismissDisclaimer}
      >
        <span aria-hidden="true">×</span>
      </button>
    </div>
  )
}
