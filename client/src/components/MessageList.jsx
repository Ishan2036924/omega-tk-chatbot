/**
 * Scrollable message list that auto-scrolls to the bottom whenever
 * new messages arrive or the thinking indicator appears.
 * Contains inline sub-components for each message type.
 */
import { useEffect, useRef, useState } from 'react'
import CodeBlock from './CodeBlock.jsx'
import TextShimmer from './TextShimmer.jsx'

// ── Sub-components ────────────────────────────────────────────────────────────

/** User's message bubble — right-aligned with a subtle dark background. */
function UserMessage({ text }) {
  return (
    <div className="flex justify-end mb-6">
      <div className="bg-[#2f2f2f] rounded-2xl px-4 py-3 max-w-[80%] text-sm text-gray-100 leading-relaxed whitespace-pre-wrap">
        {text}
      </div>
    </div>
  )
}

/** Amber warning box shown when a guardrail blocks the query. */
function FallbackBox({ message }) {
  const parts = message.split(/(https?:\/\/\S+)/g)
  return (
    <div className="bg-amber-950/50 border border-amber-600/50 rounded-xl px-4 py-3 text-sm text-amber-200 leading-relaxed">
      <span className="font-semibold text-amber-400 mr-2">⚠</span>
      {parts.map((part, i) =>
        part.match(/^https?:\/\//) ? (
          <a key={i} href={part} target="_blank" rel="noreferrer" className="underline hover:text-amber-100 break-all">
            {part}
          </a>
        ) : (
          part
        )
      )}
    </div>
  )
}

/**
 * Bot response — renders a fallback warning, explanation-only, or
 * explanation + code block. Empty code fields are silently omitted.
 */
function BotMessage({ data }) {
  if (data.is_fallback) {
    return (
      <div className="mb-6">
        <FallbackBox message={data.fallback_message} />
      </div>
    )
  }

  return (
    <div className="mb-6 space-y-3">
      {data.explanation && (
        <p className="text-sm text-gray-200 leading-relaxed">{data.explanation}</p>
      )}
      {/* Only render code block when there's actual code */}
      {data.code && (
        <CodeBlock code={data.code} language={data.language ?? 'python'} />
      )}
      {!data.explanation && !data.code && (
        <p className="text-sm text-gray-500 italic">No response content.</p>
      )}
      {data.attempts > 1 && (
        <p className="text-xs text-gray-600 select-none">
          ✓ Validated after {data.attempts} attempts
        </p>
      )}
    </div>
  )
}

/** Status messages that cycle every 2 s while waiting for a response. */
const STATUS_MESSAGES = [
  'Thinking...',
  'Searching documentation...',
  'Retrieving relevant code...',
  'Generating response...',
  'Validating output...',
]

/**
 * Animated loading indicator: shimmer text that cycles through status messages.
 * Resets to "Thinking..." each time it mounts (i.e. each new request).
 */
function ThinkingIndicator() {
  const [idx, setIdx] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => {
      setIdx((i) => (i + 1) % STATUS_MESSAGES.length)
    }, 2000)
    return () => clearInterval(timer)
  }, [])

  return (
    <div className="mb-6">
      <div className="inline-flex items-center gap-2.5 bg-[#1e1e1e] border border-[#2a2a2a] rounded-2xl px-4 py-3">
        {/* Pulsing ping dot */}
        <span className="relative flex h-2 w-2 flex-shrink-0">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-gray-500 opacity-60" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-gray-600" />
        </span>
        <TextShimmer className="font-mono text-sm" duration={1.5}>
          {STATUS_MESSAGES[idx]}
        </TextShimmer>
      </div>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

/**
 * @param {{
 *   messages: Array<{role: 'user'|'bot', text?: string, data?: object}>,
 *   isLoading: boolean
 * }} props
 */
export default function MessageList({ messages, isLoading }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  return (
    <div className="max-w-3xl mx-auto w-full px-4 pt-8 pb-4">
      {messages.map((msg, i) =>
        msg.role === 'user' ? (
          <UserMessage key={i} text={msg.text} />
        ) : (
          <BotMessage key={i} data={msg.data} />
        )
      )}
      {isLoading && <ThinkingIndicator />}
      <div ref={bottomRef} />
    </div>
  )
}
