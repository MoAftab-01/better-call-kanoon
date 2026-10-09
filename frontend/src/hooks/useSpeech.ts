/**
 * Web Speech API: speech recognition (input) and speech synthesis (output).
 *
 * Both are feature-detected and both degrade honestly. A browser without them
 * gets a disabled control with an explanation, never a thrown error and never a
 * control that silently does nothing.
 *
 * Note on what this stage can honestly do: speech *synthesis* works today and
 * can read a message aloud. Speech *recognition* is wired up, but Stage 1 has no
 * answering endpoint, so the transcript fills the composer rather than producing
 * an answer. Nothing here ever fabricates a reply.
 *
 * The `SpeechRecognition` types are not in the standard DOM lib yet, so the two
 * vendor-prefixed shapes are declared locally rather than suppressed with `any`.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { defaultLocaleFor } from '../i18n'
import type { LanguageCode } from './useLanguage'

/* ------------------------------------------------------------------ types */

interface SpeechRecognitionAlternativeLike {
  readonly transcript: string
}
interface SpeechRecognitionResultLike {
  readonly isFinal: boolean
  readonly length: number
  readonly [index: number]: SpeechRecognitionAlternativeLike
}
interface SpeechRecognitionResultListLike {
  readonly length: number
  readonly [index: number]: SpeechRecognitionResultLike
}
interface SpeechRecognitionEventLike extends Event {
  readonly resultIndex: number
  readonly results: SpeechRecognitionResultListLike
}
interface SpeechRecognitionErrorEventLike extends Event {
  readonly error: string
}

/** The subset of `SpeechRecognition` this app uses. */
interface SpeechRecognitionLike extends EventTarget {
  lang: string
  continuous: boolean
  interimResults: boolean
  maxAlternatives: number
  start(): void
  stop(): void
  abort(): void
  onresult: ((event: SpeechRecognitionEventLike) => void) | null
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null
  onend: (() => void) | null
  onstart: (() => void) | null
}
type SpeechRecognitionFactory = new () => SpeechRecognitionLike

/** Read a vendor-prefixed constructor off `window` without asserting `any`. */
function readWindow<K extends string>(key: K): unknown {
  return (window as unknown as Record<K, unknown>)[key]
}

/** `SpeechRecognition` in Chromium, `webkitSpeechRecognition` in Safari. */
function findRecognitionFactory(): SpeechRecognitionFactory | null {
  for (const key of ['SpeechRecognition', 'webkitSpeechRecognition'] as const) {
    const candidate = readWindow(key)
    if (typeof candidate === 'function') return candidate as SpeechRecognitionFactory
  }
  return null
}

/** The recognised subset of `SpeechSynthesisError`. */
export type SpeechErrorCode = 'unsupported' | 'denied' | 'no-voice' | 'failed'

function classifySpeechError(error: string): SpeechErrorCode {
  switch (error) {
    case 'not-allowed':
    case 'service-not-allowed':
      return 'denied'
    case 'no-speech':
    case 'audio-capture':
      return 'no-voice'
    case 'language-unavailable':
    case 'voice-unavailable':
      return 'unsupported'
    default:
      return 'failed'
  }
}

/* ------------------------------------------------------------------- hook */

export interface UseSpeechOptions {
  language: LanguageCode
  /** Playback rate multiplier, from `PublicConfig.speech_rates`. */
  rate: number
  /** Whether the user has switched read-aloud on. */
  enabled: boolean
}

export interface UseSpeech {
  /** `true` when this browser exposes `SpeechRecognition`. */
  recognitionSupported: boolean
  /** `true` when this browser exposes `speechSynthesis`. */
  synthesisSupported: boolean
  /** `true` while the microphone is actively listening. */
  listening: boolean
  /** `true` while an utterance is being spoken. */
  speaking: boolean
  /** The active transcript while listening, for live feedback. */
  interimTranscript: string
  /**
   * The most recent finalised transcript.
   *
   * Set once when recognition ends on a final result, then consumed and cleared
   * by the composer. Latched rather than transient so a final chunk arriving in
   * the same tick as `onend` cannot be missed.
   */
  finalTranscript: string
  /** A recognised failure reason, or `null`. Never a raw error string. */
  errorReason: SpeechErrorCode | null
  startListening: () => void
  stopListening: () => void
  /** Speak `text`. A no-op when synthesis is unavailable or already busy. */
  speak: (text: string) => void
  cancelSpeech: () => void
  /** Clear `finalTranscript` after the composer has consumed it. */
  clearFinalTranscript: () => void
}

/**
 * Speech recognition + synthesis, feature-detected.
 *
 * Both `Recognition` and `SpeechSynthesis` objects are long-lived and must be
 * torn down on unmount, or the browser keeps a microphone indicator lit after the
 * user has navigated away.
 */
export function useSpeech({ language, rate, enabled }: UseSpeechOptions): UseSpeech {
  const [listening, setListening] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [interimTranscript, setInterimTranscript] = useState('')
  const [finalTranscript, setFinalTranscript] = useState('')
  const [errorReason, setErrorReason] = useState<SpeechErrorCode | null>(null)

  // Feature detection runs once: these capabilities cannot appear mid-session.
  const capabilities = useMemo(
    () => ({
      recognition: findRecognitionFactory(),
      synthesis:
        typeof window !== 'undefined' && typeof window.speechSynthesis?.speak === 'function',
    }),
    [],
  )

  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null)
  /**
   * Whether a session is open, readable synchronously.
   *
   * `setListening` is asynchronous, so it cannot answer "is one already
   * running?" within the same tick. Every place that sets `listening` must set
   * this too, or the two drift and `startListening` either refuses a legitimate
   * start or lets a second one through.
   */
  const listeningRef = useRef(false)

  // Keep the newest values reachable from the recognition callbacks, which are
  // registered once and would otherwise close over a stale language.
  const languageRef = useRef(language)
  const rateRef = useRef(rate)
  languageRef.current = language
  rateRef.current = rate

  /* ------------------------------------------------------- recognition */

  // Build the recognition object once and keep its handlers current.
  useEffect(() => {
    const factory = capabilities.recognition
    if (!factory) return

    const recognition = new factory()
    recognition.continuous = false
    recognition.interimResults = true
    recognition.maxAlternatives = 1

    recognition.onstart = () => {
      setErrorReason(null)
      setInterimTranscript('')
      listeningRef.current = true
      setListening(true)
    }

    recognition.onresult = (event) => {
      let interim = ''
      let final = ''
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i]
        if (!result) continue
        const text = result[0]?.transcript ?? ''
        if (result.isFinal) final += text
        else interim += text
      }
      if (interim !== '') setInterimTranscript(interim)
      // Latch the final chunk now: `onend` fires immediately afterwards and
      // clears the interim echo, so latching is what keeps the text alive.
      if (final.trim() !== '') setFinalTranscript(final.trim())
    }

    recognition.onerror = (event) => {
      setErrorReason(classifySpeechError(event.error))
      setInterimTranscript('')
    }

    recognition.onend = () => {
      listeningRef.current = false
      setListening(false)
      setInterimTranscript('')
    }

    recognitionRef.current = recognition
    return () => {
      listeningRef.current = false
      recognition.onresult = null
      recognition.onerror = null
      recognition.onend = null
      recognition.onstart = null
      try {
        recognition.abort()
      } catch {
        // Already stopped. Nothing to release.
      }
      recognitionRef.current = null
    }
  }, [capabilities.recognition])

  const startListening = useCallback(() => {
    const recognition = recognitionRef.current
    // `listeningRef` rather than `listening`: this button is now a real toggle
    // and stays enabled while listening, so a fast second click can arrive
    // before React has committed the state update. The ref flips synchronously
    // and closes the double-start race in the same tick.
    if (!recognition || listeningRef.current) return
    listeningRef.current = true
    setErrorReason(null)
    recognition.lang = defaultLocaleFor(languageRef.current)
    try {
      recognition.start()
    } catch {
      // `start()` throws if a session is already running. Treat it as a no-op
      // rather than surfacing a synthetic error to the user.
      listeningRef.current = false
      setListening(false)
    }
  }, [])

  const stopListening = useCallback(() => {
    const recognition = recognitionRef.current
    if (!recognition) return
    try {
      recognition.stop()
    } catch {
      // Not running; nothing to stop.
    }
    listeningRef.current = false
    setListening(false)
  }, [])

  // Escape releases the microphone, as a keyboard equivalent to pressing the
  // mic button again. Recognition can stall without ever firing `onend` (a
  // network blip against the browser's speech service, for instance), which
  // would otherwise leave the user holding an open session with only a reload
  // to end it. Matches the Escape handler in `EmergencyContacts`.
  useEffect(() => {
    if (!listening) return

    function onKeyDown(event: KeyboardEvent): void {
      if (event.key === 'Escape') stopListening()
    }

    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [listening, stopListening])

  /* ---------------------------------------------------------- synthesis */

  const cancelSpeech = useCallback(() => {
    if (!capabilities.synthesis) return
    window.speechSynthesis.cancel()
    utteranceRef.current = null
    setSpeaking(false)
  }, [capabilities.synthesis])

  const speak = useCallback(
    (text: string) => {
      if (!capabilities.synthesis || text.trim() === '') return
      // Replace anything currently being spoken rather than queueing behind it.
      window.speechSynthesis.cancel()
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = defaultLocaleFor(languageRef.current)
      utterance.rate = rateRef.current
      utterance.onstart = () => setSpeaking(true)
      utterance.onend = () => {
        setSpeaking(false)
        utteranceRef.current = null
      }
      utterance.onerror = () => {
        setSpeaking(false)
        utteranceRef.current = null
      }
      utteranceRef.current = utterance
      window.speechSynthesis.speak(utterance)
    },
    [capabilities.synthesis],
  )

  // Turning read-aloud off must actually silence the speaker.
  useEffect(() => {
    if (!enabled) cancelSpeech()
  }, [enabled, cancelSpeech])

  // Release the speech engine on unmount.
  useEffect(() => () => {
    if (capabilities.synthesis) window.speechSynthesis.cancel()
  }, [capabilities.synthesis])

  const clearFinalTranscript = useCallback(() => setFinalTranscript(''), [])

  return {
    recognitionSupported: capabilities.recognition !== null,
    synthesisSupported: capabilities.synthesis,
    listening,
    speaking,
    interimTranscript,
    finalTranscript,
    errorReason,
    startListening,
    stopListening,
    speak,
    cancelSpeech,
    clearFinalTranscript,
  }
}
