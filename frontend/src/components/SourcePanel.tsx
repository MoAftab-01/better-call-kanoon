import { BookOpen, FileText, Link, Phone, Quote, ShieldCheck } from 'lucide-react'

export default function SourcePanel() {
  return (
    <aside className="reference-column" aria-label="Sources and upcoming voice features">
      <section className="sources-panel" id="sources" aria-labelledby="sources-title" tabIndex={-1}>
        <header className="panel-header">
          <div className="panel-title"><BookOpen size={17} aria-hidden="true" /><h2 id="sources-title">Sources & citations</h2></div>
        </header>
        <div className="sources-content">
          <span className="coming-soon">COMING SOON</span>
          <div className="source-emblem" aria-hidden="true"><BookOpen size={30} strokeWidth={1.3} /></div>
          <h3>Understanding starts with the source.</h3>
          <p>When legal retrieval is ready, this space will bring the references behind an answer into view.</p>
          <ul className="source-placeholders" aria-label="Planned source information, currently unavailable">
            <li><FileText size={15} aria-hidden="true" /><span>Acts & legislation</span><span className="placeholder-dash" aria-hidden="true">—</span></li>
            <li><Quote size={15} aria-hidden="true" /><span>Relevant provisions</span><span className="placeholder-dash" aria-hidden="true">—</span></li>
            <li><Link size={15} aria-hidden="true" /><span>Source references</span><span className="placeholder-dash" aria-hidden="true">—</span></li>
          </ul>
          <p className="source-unavailable"><ShieldCheck size={14} aria-hidden="true" />Legal retrieval is not available yet. No sources or citations are connected.</p>
        </div>
      </section>

      <section className="voice-panel" aria-labelledby="voice-title">
        <div className="voice-panel-top"><span className="voice-icon"><Phone size={18} aria-hidden="true" /></span><span className="coming-soon">COMING SOON</span></div>
        <h2 id="voice-title">A conversation, in your voice.</h2>
        <p id="voice-availability">Voice calls and microphone input are coming soon. Neither is available yet.</p>
        <button className="voice-button" type="button" disabled aria-describedby="voice-availability"><Phone size={15} aria-hidden="true" />Start voice call</button>
      </section>
    </aside>
  )
}
