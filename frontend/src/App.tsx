import { ChevronRight, CircleAlert } from 'lucide-react'
import ConnectionStatus from './components/ConnectionStatus'
import ConversationWorkspace from './components/ConversationWorkspace'
import LegalDisclaimer from './components/LegalDisclaimer'
import Sidebar from './components/Sidebar'
import SourcePanel from './components/SourcePanel'
import WelcomePanel from './components/WelcomePanel'
import { useBackendHealth } from './hooks/useBackendHealth'

export default function App() {
  const { connection, retry } = useBackendHealth()

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
            <WelcomePanel />
            {connection.state === 'disconnected' && (
              <div className="connection-notice" role="status">
                <CircleAlert size={17} aria-hidden="true" />
                <p>{connection.detail} You can still explore this workspace.</p>
              </div>
            )}
            <div className="workspace-grid">
              <ConversationWorkspace />
              <SourcePanel />
            </div>
            <LegalDisclaimer />
          </main>
        </div>
      </div>
    </>
  )
}
