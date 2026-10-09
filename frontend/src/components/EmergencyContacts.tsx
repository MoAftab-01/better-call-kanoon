/**
 * The emergency-helplines panel.
 *
 * Rendered as a modal dialog with a focus trap, Escape-to-close and
 * backdrop-to-close, ported from the vanilla implementation's `trapFocus`.
 *
 * Honesty rule that shapes this file: every record ships with `verified: false`,
 * so each card carries a visible "Unverified" marker plus an explanation. The
 * numbers are useful, but presenting them as authoritative would be a claim this
 * project has not earned and cannot verify without checking official sources.
 */
import { useCallback, useEffect, useRef } from 'react'

import type { ContactCard } from '../api/mappers'
import type { Strings } from '../i18n'

interface EmergencyContactsProps {
  open: boolean
  onClose: () => void
  contacts: ContactCard[]
  strings: Strings
}

export function EmergencyContacts({ open, onClose, contacts, strings }: EmergencyContactsProps) {
  const panelRef = useRef<HTMLDivElement | null>(null)
  const closeRef = useRef<HTMLButtonElement | null>(null)
  // The element that opened the dialog, so focus returns there on close.
  const openerRef = useRef<HTMLElement | null>(null)

  const handleClose = useCallback(() => {
    onClose()
    // Return focus to the control that opened the dialog.
    openerRef.current?.focus()
  }, [onClose])

  // Move focus into the dialog when it opens.
  useEffect(() => {
    if (!open) return
    openerRef.current = document.activeElement as HTMLElement | null
    closeRef.current?.focus()

    // Lock background scroll while the dialog is up, matching the vanilla panel.
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previousOverflow
    }
  }, [open])

  // Escape closes; Tab is trapped inside the dialog.
  useEffect(() => {
    if (!open) return

    function onKeyDown(event: KeyboardEvent): void {
      if (event.key === 'Escape') {
        event.preventDefault()
        handleClose()
        return
      }
      if (event.key !== 'Tab') return

      const panel = panelRef.current
      if (!panel) return
      const focusables = panel.querySelectorAll<HTMLElement>(
        'button, a[href], [tabindex]:not([tabindex="-1"])',
      )
      if (focusables.length === 0) return

      const first = focusables[0]
      const last = focusables[focusables.length - 1]
      if (!first || !last) return

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, handleClose])

  if (!open) return null

  const anyUnverified = contacts.some((contact) => !contact.verified)

  return (
    <div
      className="modal"
      id="emergency-panel"
      onClick={(event) => {
        // Clicking the backdrop closes; clicks inside the card do not.
        if (event.target === event.currentTarget) handleClose()
      }}
    >
      <div
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="emergency-title"
        ref={panelRef}
      >
        <div className="modal-head">
          <div>
            <h2 className="modal-title" id="emergency-title">
              {strings.emergencyTitle}
            </h2>
            <p className="modal-sub">{strings.emergencySub}</p>
          </div>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={handleClose}
            ref={closeRef}
            aria-label={strings.emergencyClose}
          >
            {strings.emergencyClose}
          </button>
        </div>

        {contacts.length === 0 ? (
          <p className="notice notice-warn" role="status" aria-live="polite">
            {strings.emergencyNone}
          </p>
        ) : (
          <ul className="contact-list">
            {contacts.map((contact) => (
              <li className="contact" key={contact.id}>
                <div className="contact-text">
                  <p className="contact-label">{contact.label}</p>
                  {contact.note !== '' ? <p className="contact-note">{contact.note}</p> : null}
                  {contact.source !== '' ? (
                    <p className="contact-source">{contact.source}</p>
                  ) : null}
                </div>

                {contact.dialHref !== null ? (
                  <a
                    className="contact-dial"
                    href={contact.dialHref}
                    aria-label={`${strings.callLabel} ${contact.label}: ${contact.number}`}
                  >
                    {contact.number}
                  </a>
                ) : (
                  <span className="contact-dial" aria-hidden="true">
                    {contact.number}
                  </span>
                )}

                {!contact.verified ? (
                  /* The `verified` flag is surfaced, never hidden: the number is
                     published, but it has not been checked against an official
                     Government of India source. */
                  <span
                    className="contact-unverified"
                    title={strings.unverifiedExplain}
                  >
                    {strings.unverified}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        )}

        {contacts.length > 0 && anyUnverified ? (
          <p className="notice notice-warn" role="status" aria-live="polite">
            {strings.unverifiedExplain}
          </p>
        ) : null}
      </div>
    </div>
  )
}
