import { ArrowUp, MessageSquare, Mic, Scale, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { sendQuestion, type Answer, type ChatStatus, type Message } from '../chat'

const starters = [
  { label: 'BNS commencement', question: 'What does the BNS commencement notification state?' },
  { label: 'BNSS First Schedule', question: 'What does the BNSS commencement notification say about the First Schedule entry relating to BNS section 106(2)?' },
  { label: 'BSA notification', question: 'What is stated in the BSA commencement notification?' },
]
export default function ConversationWorkspace({ connected, onSelect }: { connected: boolean; onSelect: (answer: Answer | null) => void }) {
  const [draft, setDraft] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [status, setStatus] = useState<ChatStatus | null>(null)
  const [statusError, setStatusError] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [failedQuestion, setFailedQuestion] = useState('')
  const conversation = useRef<string | null>(null)
  const controller = useRef<AbortController | null>(null)
  const sending = useRef(false)
  const sequence = useRef(0)
  const input = useRef<HTMLTextAreaElement>(null)
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!connected) return
    let active = true
    const abort = new AbortController()
    const timer = window.setTimeout(() => abort.abort(), 6000)
    fetch('/api/chat/status', { signal: abort.signal, cache: 'no-store' })
      .then(r => { if (!r.ok) throw new Error(); return r.json() })
      .then((s: ChatStatus) => { if (!s.retrieval || typeof s.available !== 'boolean') throw new Error(); setStatus(s); setStatusError(false) })
      .catch(() => { if (active) setStatusError(true) })
      .finally(() => window.clearTimeout(timer))
    return () => { active = false; window.clearTimeout(timer); abort.abort() }
  }, [connected])
  useEffect(() => { end.current?.scrollIntoView({ block: 'nearest' }) }, [messages, busy])
  useEffect(() => () => { controller.current?.abort() }, [])
  async function submit(question = draft, retry = false) {
    const text = question.trim()
    if (!text || sending.current || !connected || !status?.available) return
    sending.current = true
    setBusy(true); setError(''); setFailedQuestion(''); setDraft('')
    const serial = ++sequence.current
    const abort = new AbortController(); controller.current = abort
    const timer = window.setTimeout(() => abort.abort(), 30000)
    if (!retry) setMessages(old => [...old, { id: crypto.randomUUID(), role: 'user' as const, content: text }].slice(-40))
    try {
      const result = await sendQuestion(text, conversation.current, messages, abort.signal)
      if (sequence.current !== serial) return
      conversation.current = result.conversation_id
      setMessages(old => [...old, { id: crypto.randomUUID(), role: 'assistant' as const, content: result.answer, result }].slice(-40))
      onSelect(result)
    } catch (e) {
      if (sequence.current !== serial) return
      setFailedQuestion(text)
      setError(abort.signal.aborted ? 'The request timed out. You can retry.' : e instanceof Error ? e.message : 'Connection failed. Please retry.')
    } finally {
      window.clearTimeout(timer)
      if (sequence.current === serial) { sending.current = false; setBusy(false) }
    }
  }
  function clear() {
    sequence.current++; controller.current?.abort(); sending.current = false
    setBusy(false); setMessages([]); setDraft(''); setError(''); setFailedQuestion('')
    conversation.current = null; onSelect(null); input.current?.focus()
  }
  const unavailable = !connected ? 'Backend disconnected. Use Retry in the connection indicator.'
    : statusError ? 'Chat service unavailable. Refresh the backend connection to retry.'
      : !status ? 'Checking chat services...' : !status.available ? 'Chat service is unavailable.' : ''
  return (
    <section className="conversation-panel" id="workspace" aria-labelledby="conversation-title" tabIndex={-1}>
      <header className="panel-header">
        <div className="panel-title"><MessageSquare size={17} aria-hidden="true" /><h2 id="conversation-title">Your conversation</h2></div>
        <button className="clear-chat" type="button" onClick={clear} aria-label="Clear conversation"><Trash2 size={14} />Clear</button>
      </header>
      {!messages.length && <div className="conversation-empty">
        <div className="empty-emblem" aria-hidden="true"><Scale size={29} strokeWidth={1.4} /></div>
        <p className="section-kicker">RESEARCH WITH THE SOURCE IN VIEW</p>
        <h3>Ask what the document says.</h3>
        <p>Explore the original BNS, BNSS and BSA commencement notifications. Answers describe archival text, not your current legal rights.</p>
        <div className="starter-area"><p>Start with an available source.</p><div className="starter-list">
          {starters.map(s => <button className="starter-button" type="button" key={s.label} onClick={() => { setDraft(s.question); input.current?.focus() }}>{s.label}</button>)}
        </div></div>
      </div>}
      {!!messages.length && <div className="message-list" role="log" aria-label="Conversation messages" aria-live="polite" aria-busy={busy}>
        {messages.map(m => <article key={m.id} className={'chat-message ' + m.role}>
          <strong>{m.role === 'user' ? 'You' : 'Kanoon'}</strong>
          {m.result && <span className="evidence-badge">{m.result.evidence_status.replaceAll('_', ' ')}</span>}
          <p>{m.content}</p>
          {m.result && <>
            <p className="answer-mode">{m.result.provider.status === 'completed' ? 'Groq evidence selection' : 'Extractive source response'} · {m.result.retrieval_mode.toUpperCase()} · currentness unknown</p>
            <button type="button" className="source-select" onClick={() => onSelect(m.result!)}>View sources for this answer ({m.result.citations.length})</button>
            <details className="answer-warnings"><summary>Scope and uncertainty</summary><ul>{m.result.warnings.map(w => <li key={w}>{w}</li>)}</ul></details>
          </>}
        </article>)}
        <div ref={end} />
      </div>}
      {busy && <p className="chat-progress" role="status">Retrieving and checking source evidence...</p>}
      {error && <div className="chat-error" role="alert"><p>{error}</p><button type="button" disabled={busy || !connected} onClick={() => void submit(failedQuestion, true)}>Retry question</button></div>}
      <form className="composer" onSubmit={e => { e.preventDefault(); void submit() }} aria-label="Legal research question">
        <div className="composer-label-row"><label htmlFor="legal-question">Ask an archival legal research question</label><span className="draft-label">ENGLISH</span></div>
        <div className="composer-input"><textarea ref={input} id="legal-question" name="question" value={draft} onChange={e => setDraft(e.target.value)} maxLength={2000} rows={3}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void submit() } }}
          placeholder="What does S.O. 850(E) say about commencement?" aria-describedby="answer-availability draft-privacy" />
          <div className="composer-toolbar"><span className="character-count">{draft.length.toLocaleString('en-IN')} / 2,000</span><div className="composer-actions">
            <button className="mic-button" type="button" disabled aria-label="Voice input coming soon" aria-describedby="voice-availability"><Mic size={17} aria-hidden="true" /></button>
            <button className="send-button" type="submit" disabled={busy || !draft.trim() || !!unavailable} aria-label="Send question"><ArrowUp size={19} aria-hidden="true" /></button>
          </div></div>
        </div>
        <p className="composer-notice" id="answer-availability" role="status">{unavailable || status?.answer_mode}{status && !status.retrieval.passages && ' No local corpus is loaded; unsupported questions receive an insufficient-evidence response.'}</p>
        <p className="draft-privacy" id="draft-privacy">Questions go to your local backend and, when configured, Groq. History stays in browser memory (40 messages, six recent turns sent). Clear or reload to remove it.</p>
      </form>
    </section>
  )
}
