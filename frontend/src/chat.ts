export interface Citation {
  id: string; candidate_id: string; document_id: string; title: string; instrument: string
  source_url: string | null; issuing_authority: string | null; publication_date: string | null
  pdf_page: number; start_line: number; end_line: number; quote: string
  raw_sha256: string; processed_sha256: string; text_sha256: string
}
export interface Answer {
  answer: string; conversation_id: string
  evidence_status: 'VERIFIED_REVIEWED' | 'ARCHIVAL_UNVERIFIED' | 'INSUFFICIENT_EVIDENCE'
  citations: Citation[]; provider: { status: string; generation_mode: string; model: string | null }
  warnings: string[]; legal_currentness: string; retrieval_mode: string
}
export interface ChatStatus {
  available: boolean; answer_mode: string; provider_configured: boolean
  retrieval: { passages: number; mode: string; detail: string }
}
export interface Message { id: string; role: 'user' | 'assistant'; content: string; result?: Answer }
export function officialSource(url: string | null): string | undefined {
  if (!url) return undefined
  try {
    const parsed = new URL(url)
    if (parsed.protocol !== 'https:' || parsed.username || parsed.password) return undefined
    if (!parsed.hostname.endsWith('.gov.in') && !parsed.hostname.endsWith('.nic.in')) return undefined
    return parsed.href
  } catch { return undefined }
}
export async function sendQuestion(message: string, conversationId: string | null, messages: Message[], signal: AbortSignal): Promise<Answer> {
  const response = await fetch('/api/chat', {
    method: 'POST', signal, headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ message, conversation_id: conversationId,
      history: messages.slice(-6).map(m => ({ role: m.role, content: m.content.slice(0, 1200) })) }),
  })
  let data
  try { data = await response.json() } catch { throw new Error('The backend returned an unreadable response. Please retry.') }
  if (!response.ok) throw new Error(data?.error?.message || 'The request failed. Please retry.')
  if (typeof data.answer !== 'string' || typeof data.conversation_id !== 'string' || !Array.isArray(data.citations) || !Array.isArray(data.warnings) || !data.provider) {
    throw new Error('The backend returned an unexpected chat response.')
  }
  return data as Answer
}
