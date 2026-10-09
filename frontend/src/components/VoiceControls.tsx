/**
 * Voice settings: the read-aloud toggle and the speech-rate picker.
 *
 * Both controls are feature-detected. Without `speechSynthesis` the toggle is
 * disabled and the hint says why, instead of rendering a switch that silently
 * does nothing.
 *
 * The rate list comes from `PublicConfig.speech_rates`; the remembered choice is
 * restored only when the API still offers that value, so a backend change can
 * never leave the picker pointing at a rate that no longer exists.
 */
import { useId } from 'react'

import type { Strings } from '../i18n'

interface VoiceControlsProps {
  synthesisSupported: boolean
  readAloud: boolean
  onReadAloudChange: (value: boolean) => void
  rates: number[]
  rate: number
  onRateChange: (rate: number) => void
  strings: Strings
}

export function VoiceControls({
  synthesisSupported,
  readAloud,
  onReadAloudChange,
  rates,
  rate,
  onRateChange,
  strings,
}: VoiceControlsProps) {
  const rateId = useId()

  return (
    <section className="voice" aria-labelledby="voice-heading">
      <h2 className="section-heading" id="voice-heading">
        {strings.sectionVoice}
      </h2>
      <div className="voice-row">
        <label className="toggle">
          <input
            type="checkbox"
            checked={readAloud}
            disabled={!synthesisSupported}
            onChange={(event) => onReadAloudChange(event.target.checked)}
          />
          <span className="toggle-track" aria-hidden="true">
            <span className="toggle-thumb" />
          </span>
          <span className="toggle-label">{strings.readAloud}</span>
        </label>

        <label className="field" htmlFor={rateId}>
          <span className="field-label">{strings.speechRate}</span>
          <select
            id={rateId}
            value={String(rate)}
            disabled={rates.length === 0}
            onChange={(event) => onRateChange(Number(event.target.value))}
          >
            {rates.map((value) => (
              <option key={value} value={String(value)}>
                {value.toFixed(2)}×
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="hint">
        {synthesisSupported ? strings.voiceHint : strings.voiceUnavailable}
      </p>
    </section>
  )
}
