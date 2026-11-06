import { BookOpen, Phone } from 'lucide-react'
import { officialSource, type Answer } from '../chat'
export default function SourcePanel({ answer }: { answer: Answer | null }) {
  return <aside className="reference-column" aria-label="Sources and upcoming voice features">
    <section className="sources-panel" id="sources" aria-labelledby="sources-title" tabIndex={-1}>
      <header className="panel-header"><div className="panel-title"><BookOpen size={17} aria-hidden="true" /><h2 id="sources-title">Sources & citations</h2></div></header>
      <div className="sources-content">
        {!answer ? <><div className="source-emblem" aria-hidden="true"><BookOpen size={30} strokeWidth={1.3} /></div><h3>Evidence beside the answer.</h3><p>Ask a supported question, then select an answer to inspect its actual sources. No sources are selected yet.</p></>
          : !answer.citations.length ? <p>No adequate evidence was found for this answer. No citations are invented.</p>
            : answer.citations.map(c => <article className="citation-card" key={c.candidate_id}>
              <span className="evidence-badge">ARCHIVAL · UNREVIEWED</span>
              <h3>[{c.id}] {c.instrument || c.title}</h3><p>{c.title}</p>
              <p>{c.issuing_authority}<br />Publication: {c.publication_date || 'Unknown'}<br />Physical PDF page {c.pdf_page}, normalized lines {c.start_line}–{c.end_line}</p>
              {officialSource(c.source_url) && <a href={officialSource(c.source_url) + '#page=' + c.pdf_page} target="_blank" rel="noopener noreferrer">Open official source PDF</a>}
              <details><summary>Exact cited text</summary><blockquote>{c.quote}</blockquote></details>
              <details><summary>Evidence binding</summary><dl><dt>Document</dt><dd>{c.document_id}</dd><dt>Candidate (not approved)</dt><dd>{c.candidate_id}</dd><dt>Raw PDF SHA-256</dt><dd>{c.raw_sha256}</dd><dt>Processed SHA-256</dt><dd>{c.processed_sha256}</dd><dt>Exact text SHA-256</dt><dd>{c.text_sha256}</dd></dl></details>
            </article>)}
        <p className="source-unavailable">Source identity does not prove legal correctness or current applicability. Existing proposals remain unapproved.</p>
      </div>
    </section>
    <section className="voice-panel" aria-labelledby="voice-title"><div className="voice-panel-top"><span className="voice-icon"><Phone size={18} aria-hidden="true" /></span><span className="coming-soon">COMING SOON</span></div><h2 id="voice-title">A conversation, in your voice.</h2><p id="voice-availability">Voice calls and microphone input are future features. Neither is available.</p><button className="voice-button" type="button" disabled aria-describedby="voice-availability"><Phone size={15} aria-hidden="true" />Start voice call</button></section>
  </aside>
}
