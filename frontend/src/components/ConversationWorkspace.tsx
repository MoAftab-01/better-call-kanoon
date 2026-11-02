import { ArrowUp, BriefcaseBusiness, House, LockKeyhole, MessageSquare, Mic, Scale, ShoppingBag } from 'lucide-react'
import { useRef, useState } from 'react'

const starters = [
  { label: 'Consumer rights', question: 'What can I do if a product I bought is defective?', Icon: ShoppingBag },
  { label: 'Workplace concerns', question: 'What should I understand about my rights at work?', Icon: BriefcaseBusiness },
  { label: 'Housing & tenancy', question: 'What should I look for before signing a rental agreement?', Icon: House },
]

export default function ConversationWorkspace() {
  const [draft, setDraft] = useState('')
  const input = useRef<HTMLTextAreaElement>(null)

  function chooseStarter(question: string) {
    setDraft(question)
    input.current?.focus()
  }

  return (
    <section className="conversation-panel" id="workspace" aria-labelledby="conversation-title" tabIndex={-1}>
      <header className="panel-header">
        <div className="panel-title"><MessageSquare size={17} aria-hidden="true" /><h2 id="conversation-title">Your conversation</h2></div>
        <span className="quiet-label"><span aria-hidden="true" /> Not started</span>
      </header>

      <div className="conversation-empty">
        <div className="empty-emblem" aria-hidden="true"><Scale size={29} strokeWidth={1.4} /></div>
        <p className="section-kicker">A GOOD PLACE TO BEGIN</p>
        <h3>Every question deserves clarity.</h3>
        <p>Your conversation will appear here when AI answers are available.
          For now, take a look around and draft a question.</p>
        <div className="starter-area">
          <p>Need a starting point? Try a topic.</p>
          <div className="starter-list">
            {starters.map(({ label, question, Icon }) => (
              <button className="starter-button" type="button" key={label} onClick={() => chooseStarter(question)}>
                <Icon size={14} aria-hidden="true" />{label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <form className="composer" onSubmit={(event) => event.preventDefault()} aria-label="Question draft">
        <div className="composer-label-row">
          <label htmlFor="legal-question">Draft your legal question</label>
          <span className="draft-label">DRAFT ONLY</span>
        </div>
        <div className="composer-input">
          <textarea
            ref={input}
            id="legal-question"
            name="question"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            maxLength={2000}
            rows={3}
            placeholder="What would you like to understand about Indian law?"
            aria-describedby="answer-availability draft-privacy"
          />
          <div className="composer-toolbar">
            <span className="character-count">{draft.length.toLocaleString('en-IN')} / 2,000</span>
            <div className="composer-actions">
              <button className="mic-button" type="button" disabled aria-label="Voice input coming soon" aria-describedby="voice-availability">
                <Mic size={17} aria-hidden="true" />
              </button>
              <button className="send-button" type="submit" disabled aria-label="Send question unavailable" aria-describedby="answer-availability">
                <ArrowUp size={19} aria-hidden="true" />
              </button>
            </div>
          </div>
        </div>
        <p className="composer-notice" id="answer-availability"><LockKeyhole size={12} aria-hidden="true" /> AI answers are not available yet. Sending is disabled.</p>
        <p className="draft-privacy" id="draft-privacy">Your draft stays in this tab and is not sent or saved.</p>
      </form>
    </section>
  )
}
