import { Info } from 'lucide-react'

export default function LegalDisclaimer() {
  return (
    <footer className="legal-disclaimer" id="about" tabIndex={-1}>
      <Info size={16} aria-hidden="true" />
      <div>
        <h2>Information to help you understand. Not a substitute for a lawyer.</h2>
        <p>Better Call Kanoon is being built as a legal-information guide, not a licensed lawyer.
          For advice about your situation, consult a qualified legal professional.</p>
      </div>
      <span className="footer-wordmark" aria-hidden="true">Kanoon<span>.</span></span>
    </footer>
  )
}
