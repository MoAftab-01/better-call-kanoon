/**
 * The question composer: microphone, textarea, character counter and send button.
 *
 * The textarea is a real, typeable input. Stage 1 has no answering endpoint, so
 * submitting produces an honest "arrives in a later stage" notice and nothing
 * else — there is deliberately no `/api/chat` call here and no fabricated reply.
 *
 * The microphone is feature-detected. When `SpeechRecognition` is missing the
 * button stays disabled and the hint explains why, instead of throwing or
 * pretending to listen.
 */
import { useCallback, useId } from 'react'

import type { Strings } from '../i18n'

interface ComposerProps {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  /**
   * Ref to the textarea, so a starter-card click can hand focus back to it.
   * Focus stays in the input the whole time, which is what a screen-reader user
   * expects after activating a one-tap suggestion.
   */
  inputRef: React.RefObject<HTMLTextAreaElement | null>
  /** `PublicConfig.max_input_length`; `0` means no advertised limit. */
  maxLength: number
  /** Inline validation / status text. Empty hides the notice. */
  notice: string
  /** `true` renders the notice in the warning style. */
  noticeIsWarning: boolean
  strings: Strings
  recognitionSupported: boolean
  listening: boolean
  interimTranscript: string
  onStartListening: () => void
  onStopListening: () => void
}

export function Composer({
  value,
  onChange,
  onSubmit,
  inputRef,
  maxLength,
  notice,
  noticeIsWarning,
  strings,
  recognitionSupported,
  listening,
  interimTranscript,
  onStartListening,
  onStopListening,
}: ComposerProps) {
  // Stable ids so the <label for> and aria-describedby wiring survives
  // re-renders without depending on hardcoded element ids.
  const inputId = useId()
  const hintId = useId()
  const metaId = useId()

  const used = value.length
  const over = maxLength > 0 && used > maxLength
  const metaText = maxLength > 0 ? `${used} / ${maxLength}` : String(used)

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
      // Enter submits; Shift+Enter inserts a newline — the usual chat convention.
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault()
        onSubmit()
      }
    },
    [onSubmit],
  )

  const hintText = recognitionSupported
    ? listening
      ? strings.listening
      : strings.micHint
    : strings.voiceUnavailable

  return (
    <div className="console">
      <div className="mic-wrap">
        <button
          type="button"
          className="mic"
          // Disabled only when the browser has no SpeechRecognition at all. A
          // running session must NOT disable the button: a disabled control
          // dispatches no clicks and leaves the tab order, so `onStopListening`
          // would be unreachable and the user would have no way to release the
          // microphone if recognition stalled without firing `onend`. Kept as a
          // real toggle, with the double-start race closed in `useSpeech`.
          disabled={!recognitionSupported}
          onClick={listening ? onStopListening : onStartListening}
          data-listening={listening ? 'true' : 'false'}
          aria-describedby={hintId}
          aria-pressed={recognitionSupported ? listening : undefined}
        >
          <svg className="mic-icon" viewBox="0 0 24 24" focusable="false" aria-hidden="true">
            <rect x="9" y="2.5" width="6" height="11" rx="3" />
            <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0" />
            <path d="M12 18v3.5" />
          </svg>
          <span className="sr-only">{strings.micLabel}</span>
        </button>
        <p className="mic-hint" id={hintId}>
          {hintText}
          {interimTranscript !== '' ? ` ${interimTranscript}` : ''}
        </p>
      </div>

      <form
        className="composer"
        noValidate
        onSubmit={(event) => {
          event.preventDefault()
          onSubmit()
        }}
      >
        <label className="sr-only" htmlFor={inputId}>
          {strings.composerLabel}
        </label>
        <textarea
          id={inputId}
          ref={inputRef}
          className="composer-input"
          name="question"
          rows={3}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={strings.composerPlaceholder}
          autoComplete="off"
          maxLength={maxLength > 0 ? maxLength : undefined}
          aria-describedby={metaId}
          aria-invalid={over || undefined}
          // Never spellcheck a legal question into something embarrassing, but
          // do allow it — a mistyped section number is worth catching.
          spellCheck
        />
        <div className="composer-foot">
          <p className="composer-meta" id={metaId} data-over={String(over)}>
            {metaText}
          </p>
          <button type="submit" className="btn btn-primary">
            {strings.composerSend}
          </button>
        </div>
      </form>

      {notice !== '' ? (
        <p
          className={`notice${noticeIsWarning ? ' notice-warn' : ''}`}
          role="status"
          aria-live="polite"
        >
          {notice}
        </p>
      ) : null}
    </div>
  )
}
