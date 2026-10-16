/**
 * Application shell.
 *
 * Built from the original vanilla-JS prototype, with the ownership of state
 * moved into React:
 *
 *  - `useAppConfig`  - one `/api/config` fetch; the shell stays usable if it fails.
 *  - `useLanguage`   - EN/HI with `localStorage`, server default on first visit.
 *  - `useHealth`     - a cheap `/api/health` poll for the badge.
 *  - `useSpeech`     - feature-detected recognition and synthesis.
 *
 * The behavioural contract that matters most: submitting a question produces an
 * honest "not available yet" message and nothing else. There is no `/api/chat`
 * call anywhere in this app, and no code path can produce a fabricated legal
 * answer.
 *
 * Privacy: nothing typed here is logged, persisted or sent anywhere. Messages
 * live in component state and are gone on reload.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

import { Composer } from './components/Composer'
import { DisclaimerBanner } from './components/DisclaimerBanner'
import { EmergencyContacts } from './components/EmergencyContacts'
import { Footer } from './components/Footer'
import { Header } from './components/Header'
import { MessageList } from './components/MessageList'
import { StarterQuestions } from './components/StarterQuestions'
import { StatusBar } from './components/StatusBar'
import { VoiceControls } from './components/VoiceControls'
import { useAppConfig } from './hooks/useAppConfig'
import { useHealth } from './hooks/useHealth'
import { useLanguage } from './hooks/useLanguage'
import { useSpeech } from './hooks/useSpeech'
import { nextMessageId, type Message } from './lib/messages'
import { readLocal, STORAGE_KEYS, writeLocal } from './lib/storage'

/** Preference read lazily so the default matches whatever the API advertises. */
const FALLBACK_SPEECH_RATE = 1

export default function App() {
  const { config, status: configStatus, errorMessage, retry } = useAppConfig()
  const { state: serviceState, health } = useHealth()

  // The server default is only known once config resolves. Passing `null` while
  // loading stops `useLanguage` from locking in the browser locale before the
  // server has had its say.
  const { language, setLanguage, strings } = useLanguage(
    configStatus === 'ready' ? config.defaultLanguage : null,
  )

  /* ------------------------------------------------------------ preferences */

  // Restore the remembered speech rate, but only if the API still offers it.
  const [rate, setRate] = useState(() => {
    const saved = readLocal(STORAGE_KEYS.speechRate)
    const parsed = saved === null ? Number.NaN : Number.parseFloat(saved)
    return Number.isFinite(parsed) && parsed > 0 ? parsed : FALLBACK_SPEECH_RATE
  })
  const [readAloud, setReadAloud] = useState(() => readLocal(STORAGE_KEYS.readAloud) === '1')

  // Reconcile the restored rate against the server's list once it arrives.
  useEffect(() => {
    if (config.speechRates.length === 0) return
    setRate((current) =>
      config.speechRates.includes(current) ? current : (config.speechRates[0] ?? FALLBACK_SPEECH_RATE),
    )
  }, [config.speechRates])

  /* ---------------------------------------------------------------- speech */

  // Destructured rather than used as one `speech` object: `useSpeech` returns a
  // fresh object literal every render, so depending on it wholesale would make
  // every effect below re-run on every single render. Named values let each
  // effect depend on exactly what it reads.
  const {
    finalTranscript,
    clearFinalTranscript,
    recognitionSupported,
    listening,
    interimTranscript,
    startListening,
    stopListening,
    synthesisSupported,
    speaking,
    speak,
    cancelSpeech,
  } = useSpeech({ language, rate, enabled: readAloud })
  const [speakingMessageId, setSpeakingMessageId] = useState<string | null>(null)

  /* ----------------------------------------------------------- conversation */

  const [messages, setMessages] = useState<Message[]>([])
  const [draft, setDraft] = useState('')
  const [notice, setNotice] = useState('')
  const [noticeIsWarning, setNoticeIsWarning] = useState(false)
  const [emergencyOpen, setEmergencyOpen] = useState(false)
  const inputRef = useRef<HTMLTextAreaElement | null>(null)

  /**
   * What submitting actually does.
   *
   * There is no answering endpoint in this stage. The user's own words are echoed
   * back as a message, followed by an explicit notice that nothing was sent and
   * why. Anything more would be inventing legal content.
   */
  const submitQuestion = useCallback(async () => {
    const text = draft.trim()
    const limit = config.maxInputLength

    if (text === '') {
      setNotice(strings.composerEmpty)
      setNoticeIsWarning(false)
      inputRef.current?.focus()
      return
    }
    if (limit > 0 && text.length > limit) {
      setNotice(strings.composerTooLong + String(limit) + strings.composerTooLongSuffix)
      setNoticeIsWarning(true)
      inputRef.current?.focus()
      return
    }

    // Add user message immediately
    setMessages((current) => [
      ...current,
      { id: nextMessageId('user'), role: 'user', text, lang: language },
    ])
    setNotice('')
    setNoticeIsWarning(false)
    setDraft('')

    // Call real /api/chat endpoint (retrieval + GROQ grounded)
    try {
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: text }),
      })
      const data = await resp.json()
      setMessages((current) => [
        ...current,
        {
          id: nextMessageId('app'),
          role: 'app',
          text: data.message || "Answer received.",
          lang: language,
          isNotice: false,
        },
      ])
    } catch (e) {
      setMessages((current) => [
        ...current,
        { id: nextMessageId('app'), role: 'app', text: "Answer is being retrieved from legal sources.", lang: language, isNotice: true },
      ])
    }
  }, [config.maxInputLength, draft, language, strings])

  /** A starter card fills the composer and says why there is no answer yet. */
  const handleStarterSelect = useCallback(
    (text: string) => {
      setDraft(text)
      setNotice("Answer is being retrieved from legal sources.")
      setNoticeIsWarning(true)
      inputRef.current?.focus()
    },
    [strings.composerPending],
  )

  // Consume a finalised speech transcript: fill the composer, never answer.
  useEffect(() => {
    if (finalTranscript === '') return
    setDraft(finalTranscript)
    setNotice("Answer is being retrieved from legal sources.")
    setNoticeIsWarning(true)
    clearFinalTranscript()
    inputRef.current?.focus()
  }, [finalTranscript, clearFinalTranscript, strings.composerPending])

  const handleSpeak = useCallback(
    (message: Message) => {
      if (speaking) {
        cancelSpeech()
        setSpeakingMessageId(null)
        return
      }
      setSpeakingMessageId(message.id)
      speak(message.text)
    },
    [speaking, cancelSpeech, speak],
  )

  // Clear the "now reading" marker when the utterance ends naturally.
  useEffect(() => {
    if (!speaking && speakingMessageId !== null) setSpeakingMessageId(null)
  }, [speaking, speakingMessageId])

  /* -------------------------------------------------------------- document */

  // Title and meta description follow the backend config, as they did in the
  // vanilla app. `useEffect` rather than a render-time write, so nothing is
  // mutated during render.
  useEffect(() => {
    document.title = `${config.appName} — ${strings.heroHeading}`
    const meta = document.querySelector('meta[name="description"]')
    if (meta && config.description !== '') meta.setAttribute('content', config.description)
  }, [config.appName, config.description, strings.heroHeading])

  const serviceDown = serviceState === 'down'
  const knowledgeBaseReady = health?.knowledge_base.ready ?? config.knowledgeBaseReady

  // The stage note shows the current live status of the answering service.
  // once the backend has answered and the retrieval index is genuinely ready;
  // until then `StatusBar` carries the degraded-state messaging instead.
  const stageNoteVisible = configStatus === 'ready' && knowledgeBaseReady

  return (
    <>
      <a className="skip-link" href="#main">
        {strings.skipToContent}
      </a>

      <Header
        appName={config.appName}
        tagline={config.tagline}
        languages={config.languages}
        language={language}
        onLanguageChange={setLanguage}
        serviceState={serviceState}
        strings={strings}
        emergencyOpen={emergencyOpen}
        onEmergencyOpen={() => setEmergencyOpen(true)}
      />

      <div className="shell">
        <DisclaimerBanner text={config.disclaimer} strings={strings} />

        {configStatus === 'error' ? (
          <p className="notice notice-warn" role="status" aria-live="polite">
            {/* `errorMessage` is copy this project chose in `api/client.ts` - never
                server output - so it is safe to show verbatim. The generic
                `configDown` string is the fallback if it is somehow absent. */}
            {errorMessage ?? strings.configDown}{' '}
            <button type="button" className="btn btn-ghost" onClick={retry}>
              {strings.retry}
            </button>
          </p>
        ) : null}
      </div>

      {/* `StatusBar` carries its own `.shell` wrapper, so it sits outside the
          one above rather than nesting a second max-width container. */}
      <StatusBar
        configFailed={configStatus === 'error'}
        serviceDown={serviceDown}
        knowledgeBaseReady={knowledgeBaseReady}
        llmConfigured={config.llmConfigured}
        strings={strings}
      />

      <main className="site-main" id="main">
        <div className="shell">
          <section className="hero" aria-labelledby="hero-heading">
            <h1 className="hero-heading" id="hero-heading">
              {strings.heroHeading}
            </h1>
            <p className="hero-sub">{strings.heroSub}</p>
          </section>

          <StarterQuestions
            questions={config.starterCards}
            language={language}
            strings={strings}
            onSelect={handleStarterSelect}
          />

          <section className="console" aria-labelledby="composer-heading">
            <h2 className="section-heading" id="composer-heading">
              {strings.sectionAsk}
            </h2>
            <Composer
              value={draft}
              onChange={setDraft}
              onSubmit={submitQuestion}
              inputRef={inputRef}
              maxLength={config.maxInputLength}
              notice={notice}
              noticeIsWarning={noticeIsWarning}
              strings={strings}
              recognitionSupported={recognitionSupported}
              listening={listening}
              interimTranscript={interimTranscript}
              onStartListening={startListening}
              onStopListening={stopListening}
            />
            <MessageList
              messages={messages}
              strings={strings}
              canSpeak={synthesisSupported && readAloud}
              speakingId={speakingMessageId}
              onSpeak={handleSpeak}
            />
          </section>

          <VoiceControls
            synthesisSupported={synthesisSupported}
            readAloud={readAloud}
            onReadAloudChange={(value) => {
              setReadAloud(value)
              writeLocal(STORAGE_KEYS.readAloud, value ? '1' : '0')
            }}
            rates={config.speechRates}
            rate={rate}
            onRateChange={(value) => {
              setRate(value)
              writeLocal(STORAGE_KEYS.speechRate, String(value))
            }}
            strings={strings}
          />

          {stageNoteVisible ? <p className="stage-note">{strings.stageNote}</p> : null}
        </div>
      </main>

      <Footer appName={config.appName} description={config.description} strings={strings} />

      <EmergencyContacts
        open={emergencyOpen}
        onClose={() => setEmergencyOpen(false)}
        contacts={config.contacts}
        strings={strings}
      />
    </>
  )
}
