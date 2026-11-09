import { useEffect, useRef, useState } from 'react'
import { Mic, Square, Volume2 } from 'lucide-react'

interface Recognition {
  lang: string; interimResults: boolean; continuous: boolean
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null
  onerror: ((event: { error: string }) => void) | null
  onend: (() => void) | null
  start(): void; stop(): void; abort(): void
}
type SpeechWindow = Window & { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition }

export function VoiceInput({ onText, disabled }: { onText: (text: string) => void; disabled: boolean }) {
  const [listening, setListening] = useState(false)
  const [notice, setNotice] = useState('')
  const [consent, setConsent] = useState(false)
  const recognition = useRef<Recognition | null>(null)
  const supported = !!((window as SpeechWindow).SpeechRecognition || (window as SpeechWindow).webkitSpeechRecognition)
  useEffect(() => () => { if (recognition.current) { recognition.current.onresult = null; recognition.current.onerror = null; recognition.current.onend = null; recognition.current.abort() } }, [])
  useEffect(() => { if (disabled && recognition.current) { recognition.current.onresult = null; recognition.current.abort() } }, [disabled])
  function start() {
    const Constructor = (window as SpeechWindow).SpeechRecognition || (window as SpeechWindow).webkitSpeechRecognition
    if (!Constructor || disabled || !consent || recognition.current) return
    const instance = new Constructor()
    recognition.current = instance
    instance.lang = 'en-IN'; instance.interimResults = false; instance.continuous = false
    instance.onresult = event => {
      if (recognition.current !== instance) return
      const text = Array.from(event.results).map(r => r[0]?.transcript || '').join(' ')
      onText(text.slice(0, 2000)); setNotice('Transcript added to the draft. Check it before sending.')
    }
    instance.onerror = event => {
      if (recognition.current !== instance) return
      recognition.current = null; instance.onresult = null
      setNotice(event.error === 'not-allowed' || event.error === 'service-not-allowed'
        ? 'Microphone permission denied. You can continue typing.'
        : event.error === 'no-speech' ? 'No speech detected. Try again or type your question.'
          : 'Speech recognition ended or is unavailable. You can continue typing.')
      setListening(false)
    }
    instance.onend = () => { if (recognition.current === instance) { recognition.current = null; setListening(false) } }
    try { instance.start(); setListening(true); setNotice('Listening. Stop when finished; nothing is sent as a question automatically.') }
    catch { recognition.current = null; setListening(false); setNotice('Could not start the microphone. Continue typing.') }
  }
  return <div className="browser-voice">
    <p id="speech-privacy">Browser voice is optional. Your browser may send audio to its speech provider; it may require an internet connection. Kanoon does not store audio.</p>
    {supported ? <>
      <label className="voice-consent"><input type="checkbox" checked={consent} disabled={listening} onChange={e => setConsent(e.target.checked)} />I agree to use browser speech recognition.</label>
      <button className="source-select" type="button" disabled={disabled || !consent} aria-pressed={listening} aria-describedby="speech-privacy" onClick={() => listening ? recognition.current?.stop() : start()}>
        {listening ? <Square size={15} /> : <Mic size={15} />}{listening ? 'Stop recording' : 'Dictate question'}</button>
      {listening && <button type="button" className="source-select" onClick={() => { if (recognition.current) { recognition.current.onresult = null; recognition.current.abort() }; setNotice('Recording cancelled.'); setListening(false) }}>Cancel recording</button>}
    </> : <p>Speech recognition is unavailable in this browser. Typed chat works normally.</p>}
    <p role="status" aria-live="polite">{notice}</p>
  </div>
}

export function ReadAloud({ text }: { text: string }) {
  const [speaking, setSpeaking] = useState(false)
  const [notice, setNotice] = useState('')
  useEffect(() => () => { if (window.speechSynthesis) window.speechSynthesis.cancel() }, [])
  if (!window.speechSynthesis || typeof window.SpeechSynthesisUtterance !== 'function') return <p>Read aloud is unavailable in this browser.</p>
  function read() {
    window.speechSynthesis.cancel()
    if (speaking) { setSpeaking(false); return }
    if (text.length > 6000) { setNotice('This response is too long for reliable browser speech. Read the complete text and sources.'); return }
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = 'en-IN'; utterance.rate = .95
    utterance.onend = () => setSpeaking(false)
    utterance.onerror = () => { setSpeaking(false); setNotice('Speech playback is unavailable. The full text remains above.') }
    setSpeaking(true); setNotice('Browser voices may use an online speech service.'); window.speechSynthesis.speak(utterance)
  }
  return <div><button type="button" className="source-select" aria-pressed={speaking} onClick={read}><Volume2 size={14} />{speaking ? 'Stop reading' : 'Read aloud'}</button><span role="status" className="answer-mode">{notice}</span></div>
}
