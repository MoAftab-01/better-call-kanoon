/**
 * A single message bubble.
 *
 * Renders message text from the caller — never invents legal answers.
 */
import type { Message } from '../lib/messages'
import type { Strings } from '../i18n'

interface MessageProps {
  message: Message
  strings: Strings
  /** `true` when speech synthesis is available, enabling the read-aloud control. */
  canSpeak: boolean
  speaking: boolean
  onSpeak: (message: Message) => void
}

/** A small speaker glyph, inline so there is no icon font and no remote asset. */
function SpeakerIcon() {
  return (
    <svg className="msg-play-icon" width="11" height="11" viewBox="0 0 12 12" aria-hidden="true">
      <path d="M2 4.5h2L6.5 2v8L4 7.5H2z" />
      <path
        d="M8.5 4a3 3 0 0 1 0 4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  )
}

export function Message({ message, strings, canSpeak, speaking, onSpeak }: MessageProps) {
  const isUser = message.role === 'user'
  const roleLabel = isUser ? strings.userMessageLabel : strings.appMessageLabel

  return (
    <li
      className={[
        'msg',
        isUser ? 'msg-user' : 'msg-app',
        message.isNotice === true ? 'msg-notice' : '',
      ]
        .filter(Boolean)
        .join(' ')}
      // `lang` makes a screen reader switch voice for Hindi text.
      lang={message.lang}
    >
      <span className="msg-role">{roleLabel}</span>
      <p className="msg-bubble">{message.text}</p>
      {!isUser && canSpeak ? (
        <button
          type="button"
          className="msg-play"
          onClick={() => onSpeak(message)}
          aria-label={`${strings.speakAgain}: ${message.text.slice(0, 60)}`}
        >
          <SpeakerIcon />
          {speaking ? strings.stopSpeaking : strings.speakAgain}
        </button>
      ) : null}
    </li>
  )
}
