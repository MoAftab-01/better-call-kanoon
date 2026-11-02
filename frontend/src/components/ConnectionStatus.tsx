import { CircleCheck, LoaderCircle, RotateCw, WifiOff } from 'lucide-react'
import type { BackendConnection } from '../hooks/useBackendHealth'

interface Props {
  connection: BackendConnection
  onRetry: () => void
}

export default function ConnectionStatus({ connection, onRetry }: Props) {
  const Icon = connection.state === 'checking'
    ? LoaderCircle
    : connection.state === 'connected' ? CircleCheck : WifiOff
  const label = connection.state === 'checking'
    ? 'Checking backend'
    : connection.state === 'connected' ? 'Backend connected' : 'Backend disconnected'

  return (
    <div className="connection-control">
      <div
        className={`connection-badge connection-${connection.state}`}
        role="status"
        aria-live="polite"
        aria-atomic="true"
        title={connection.detail}
      >
        <Icon size={14} className={connection.state === 'checking' ? 'spin' : ''} aria-hidden="true" />
        <span>{label}</span>
        <span className="sr-only">. {connection.detail}</span>
      </div>
      <button
        className="connection-retry"
        type="button"
        onClick={onRetry}
        disabled={connection.state === 'checking'}
        aria-label={connection.state === 'disconnected' ? 'Retry backend connection' : 'Refresh backend connection'}
        title={connection.state === 'disconnected' ? 'Retry backend connection' : 'Refresh backend connection'}
      >
        <RotateCw size={14} aria-hidden="true" />
        <span>{connection.state === 'disconnected' ? 'Retry' : 'Refresh'}</span>
      </button>
    </div>
  )
}
