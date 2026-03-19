import { useEffect, useRef, useState } from 'react'
import { ThumbsUp, ThumbsDown, AlertTriangle, Zap } from 'lucide-react'
import CodeBlock from './CodeBlock.jsx'
import TextShimmer from './TextShimmer.jsx'

const STATUS_MESSAGES = [
  'Thinking…',
  'Searching documentation…',
  'Retrieving relevant context…',
  'Generating response…',
  'Validating output…',
]

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
}

/* ── Typing indicator ─────────────────────────────────── */
function ThinkingIndicator() {
  const [step, setStep] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setStep(s => (s + 1) % STATUS_MESSAGES.length), 2000)
    return () => clearInterval(t)
  }, [])
  return (
    <div className="flex items-start gap-3 px-4 sm:px-6 py-2">
      <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center flex-shrink-0 mt-0.5">
        <Zap size={13} className="text-white" />
      </div>
      <div className="bg-gray-100 rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-3">
        <div className="flex gap-1">
          {[0, 1, 2].map(i => (
            <span
              key={i}
              className="w-1.5 h-1.5 rounded-full bg-gray-400 dot-bounce"
              style={{ animationDelay: `${i * 0.18}s` }}
            />
          ))}
        </div>
        <TextShimmer className="text-xs text-gray-500" duration={1.5}>
          {STATUS_MESSAGES[step]}
        </TextShimmer>
      </div>
    </div>
  )
}

/* ── Fallback box ─────────────────────────────────────── */
function FallbackBox({ message }) {
  const parts = (message ?? '').split(/(https?:\/\/[^\s]+)/g)
  return (
    <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800">
      <AlertTriangle size={14} className="flex-shrink-0 mt-0.5 text-amber-500" />
      <p className="leading-relaxed">
        {parts.map((p, i) =>
          /^https?:\/\//.test(p)
            ? <a key={i} href={p} target="_blank" rel="noreferrer" className="underline text-amber-600">{p}</a>
            : p
        )}
      </p>
    </div>
  )
}

/* ── User bubble ──────────────────────────────────────── */
function UserMessage({ msg }) {
  return (
    <div className="flex justify-end px-4 sm:px-6 py-1.5">
      <div className="max-w-[72%] sm:max-w-[65%]">
        <div className="bg-primary text-white rounded-2xl rounded-tr-sm px-4 py-3">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.text}</p>
        </div>
        <p className="text-[10px] text-gray-400 mt-1 text-right pr-1">{formatTime(msg.timestamp)}</p>
      </div>
    </div>
  )
}

/* ── Bot bubble ───────────────────────────────────────── */
function BotMessage({ msg, onFeedback }) {
  const d = msg.data ?? {}
  return (
    <div className="flex items-start gap-3 px-4 sm:px-6 py-1.5">
      {/* Avatar */}
      <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center flex-shrink-0 mt-1">
        <Zap size={13} className="text-white" />
      </div>

      <div className="flex-1 min-w-0 max-w-[85%]">
        <div className="bg-gray-100 rounded-2xl rounded-tl-sm px-4 py-3">
          {d.is_fallback ? (
            <FallbackBox message={d.fallback_message} />
          ) : (
            <div className="space-y-3">
              {d.explanation && (
                <p className="text-sm leading-relaxed text-gray-800 whitespace-pre-wrap">{d.explanation}</p>
              )}
              {d.code && <CodeBlock code={d.code} language={d.language ?? 'python'} />}
              {!d.explanation && !d.code && (
                <p className="text-sm text-gray-400 italic">No response content.</p>
              )}
              {d.attempts > 1 && (
                <p className="text-[10px] text-gray-400">✓ Validated after {d.attempts} attempts</p>
              )}
            </div>
          )}
        </div>

        {/* Timestamp + feedback row */}
        <div className="flex items-center gap-2 mt-1 ml-1">
          <span className="text-[10px] text-gray-400">{formatTime(msg.timestamp)}</span>
          {!d.is_fallback && (
            <div className="flex items-center gap-0.5">
              <button
                onClick={() => onFeedback(msg.id, 'up')}
                title="Helpful"
                className={`p-1 rounded-md transition-colors ${
                  msg.feedback === 'up'
                    ? 'text-green-600 bg-green-100'
                    : 'text-gray-400 hover:text-green-600 hover:bg-green-50'
                }`}
              >
                <ThumbsUp size={11} />
              </button>
              <button
                onClick={() => onFeedback(msg.id, 'down')}
                title="Not helpful"
                className={`p-1 rounded-md transition-colors ${
                  msg.feedback === 'down'
                    ? 'text-red-500 bg-red-100'
                    : 'text-gray-400 hover:text-red-500 hover:bg-red-50'
                }`}
              >
                <ThumbsDown size={11} />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/* ── Main list ────────────────────────────────────────── */
export default function MessageList({ messages, isLoading, onFeedback }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  return (
    <div className="py-4 space-y-0.5">
      {messages.map(msg =>
        msg.role === 'user'
          ? <UserMessage key={msg.id} msg={msg} />
          : <BotMessage key={msg.id} msg={msg} onFeedback={onFeedback} />
      )}
      {isLoading && <ThinkingIndicator />}
      <div ref={bottomRef} />
    </div>
  )
}
