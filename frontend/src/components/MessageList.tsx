/**
 * The message list.
 *
 * `aria-live="polite"` on the list container: new messages are announced without
 * stealing focus, which matters here because the composer's focus must stay in
 * the textarea while the user is typing.
 *
 * Ported behaviour note: the vanilla Stage 1 had no message list at all, because
 * there was no chat endpoint to produce entries. This one exists so the messages
 * that *are* honest — the user's own question, and the "arrives in a later stage"
 * notice — are visible and announced.
 */
import { useEffect, useRef } from 'react'

import type { Message as MessageModel } from '../lib/messages'
import type { Strings } from '../i18n'
import { Message } from './Message'

interface MessageListProps {
  messages: MessageModel[]
  strings: Strings
  canSpeak: boolean
  speakingId: string | null
  onSpeak: (message: MessageModel) => void
}

export function MessageList({
  messages,
  strings,
  canSpeak,
  speakingId,
  onSpeak,
}: MessageListProps) {
  // Keep the newest message in view as the conversation grows. Scrolling the
  // list itself (rather than a sentinel element) keeps the markup valid HTML:
  // only `<li>` may be a child of `<ul>`.
  const listRef = useRef<HTMLUListElement | null>(null)
  useEffect(() => {
    const node = listRef.current
    if (node) node.scrollTop = node.scrollHeight
  }, [messages])

  return (
    <ul className="messages" aria-live="polite" aria-relevant="additions" ref={listRef}>
      {messages.length === 0 ? <li className="msg-empty">{strings.messagesEmpty}</li> : null}
      {messages.map((message) => (
        <Message
          key={message.id}
          message={message}
          strings={strings}
          canSpeak={canSpeak}
          speaking={speakingId === message.id}
          onSpeak={onSpeak}
        />
      ))}
    </ul>
  )
}
