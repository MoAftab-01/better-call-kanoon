import { Info } from 'lucide-react'

export default function LegalDisclaimer() {
  return (
    <footer className="legal-disclaimer" id="about" tabIndex={-1}>
      <Info size={16} aria-hidden="true" />
      <div>
        <h2>Information to help you understand. Not a substitute for a lawyer.</h2>
        <p>Better Call Kanoon describes archival text, not current law or personalized legal advice.
          Research requires authorized sources. Submitted questions reach the backend and, when evidence is available and Groq is configured, Groq. Consult a qualified legal professional for your situation.</p>
      </div>
      <span className="footer-wordmark" aria-hidden="true">Kanoon<span>.</span></span>
    </footer>
  )
}
