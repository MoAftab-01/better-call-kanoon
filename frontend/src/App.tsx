import { ChevronRight, CircleAlert } from 'lucide-react'
import ConnectionStatus from './components/ConnectionStatus'
import ConversationWorkspace from './components/ConversationWorkspace'
import LegalDisclaimer from './components/LegalDisclaimer'
import Sidebar from './components/Sidebar'
import SourcePanel from './components/SourcePanel'
import WelcomePanel from './components/WelcomePanel'
import { useBackendHealth } from './hooks/useBackendHealth'
import { useResearchStatus } from './hooks/useResearchStatus'
import { useState } from 'react'
import type { Answer } from './chat'

export default function App() {
  const { connection, retry } = useBackendHealth()
  const research = useResearchStatus(connection.state === 'connected')
  const publicationPending = research.status?.research_state === 'publication_pending'
  const [selectedAnswer, setSelectedAnswer] = useState<Answer | null>(null)

  return (
    <>
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <div className="app-shell">
        <Sidebar />
        <div className="main-column">
          <header className="topbar">
            <p className="breadcrumb">Your workspace <ChevronRight size={13} aria-hidden="true" /><span>Overview</span></p>
            <ConnectionStatus connection={connection} onRetry={retry} />
          </header>
          <main id="main-content" tabIndex={-1}>
            <div className="page-heading"><span>YOUR AI GUIDE TO INDIAN LAW</span><span className="preview-badge">WORKSPACE PREVIEW</span></div>
            <WelcomePanel publicationPending={publicationPending} />
            {publicationPending && <div className="publication-notice" role="status">
              <CircleAlert size={20} aria-hidden="true" />
              <div><h2>Source publication pending</h2><p>The website is online. Legal research is not available yet. Official-source publication must be authorized before answers and citations can be provided. No private evidence is used by this public website.</p></div>
            </div>}
            {connection.state === 'disconnected' && (
              <div className="connection-notice" role="status">
                <CircleAlert size={17} aria-hidden="true" />
                <p>{connection.detail} You can still explore this workspace.</p>
              </div>
            )}
            <div className="workspace-grid">
              <ConversationWorkspace connected={connection.state === 'connected'} research={research} onSelect={setSelectedAnswer} />
              <SourcePanel answer={selectedAnswer} publicationPending={publicationPending} />
            </div>
            <LegalDisclaimer />
          </main>
        </div>
      </div>
    </>
  )
}
