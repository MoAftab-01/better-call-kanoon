import { Scale } from 'lucide-react'

export default function WelcomePanel({ publicationPending = false }: { publicationPending?: boolean }) {
  return (
    <section className="welcome-panel" aria-labelledby="welcome-title">
      <div className="welcome-copy">
        <p className="eyebrow"><span aria-hidden="true" /> A CLEARER WAY FORWARD</p>
        <h1 id="welcome-title">The law can feel complex.<br /><em>Understanding it shouldn’t.</em></h1>
        <p className="welcome-description">
          {publicationPending ? 'Welcome to Better Call AI. Explore the workspace while official-source publication is pending. Public legal research is not active.'
            : 'Welcome to Better Call AI. A research workspace for Indian legal information. Research availability depends on authorized source access.'}
        </p>
      </div>
      <div className="welcome-art" aria-hidden="true">
        <div className="art-orbit orbit-one" />
        <div className="art-orbit orbit-two" />
        <div className="art-rule rule-one" />
        <div className="art-rule rule-two" />
        <Scale size={93} strokeWidth={1} />
        <span className="art-caption">CLARITY BEGINS HERE</span>
      </div>
    </section>
  )
}
