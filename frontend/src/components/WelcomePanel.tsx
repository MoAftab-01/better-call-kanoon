import { Scale } from 'lucide-react'

export default function WelcomePanel() {
  return (
    <section className="welcome-panel" aria-labelledby="welcome-title">
      <div className="welcome-copy">
        <p className="eyebrow"><span aria-hidden="true" /> A CLEARER WAY FORWARD</p>
        <h1 id="welcome-title">The law can feel complex.<br /><em>Understanding it shouldn’t.</em></h1>
        <p className="welcome-description">
          Welcome to Better Call Kanoon. A space for your questions about Indian law,
          designed to make legal information feel more approachable.
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
