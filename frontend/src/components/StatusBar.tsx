/**
 * A slim bar that reports degraded backend state.
 *
 * Shown when `/api/config` failed, when `/api/health` reports down, or while the
 * retrieval index is still unbuilt. It is a `role="status"` polite live region so
 * the update is announced without interrupting typing.
 *
 * Every string here is copy this project wrote. Nothing from an error path is
 * rendered: no exception text, no host, no path, no stack.
 */
import type { Strings } from '../i18n'

interface StatusBarProps {
  configFailed: boolean
  serviceDown: boolean
  knowledgeBaseReady: boolean
  llmConfigured: boolean
  strings: Strings
}

export function StatusBar({
  configFailed,
  serviceDown,
  knowledgeBaseReady,
  llmConfigured,
  strings,
}: StatusBarProps) {
  // Only surface the knowledge-base state once the backend is actually
  // answering; otherwise it is noise on top of a connection error.
  const showKnowledgeBase = !configFailed && !serviceDown && !knowledgeBaseReady
  const showLlm = !configFailed && !serviceDown && !llmConfigured

  if (!configFailed && !serviceDown && !showKnowledgeBase && !showLlm) return null

  return (
    <div className="shell">
      <p className="notice notice-warn" role="status" aria-live="polite">
        {configFailed || serviceDown ? strings.statusBarUnavailableBody : strings.stageNote}
      </p>
    </div>
  )
}
