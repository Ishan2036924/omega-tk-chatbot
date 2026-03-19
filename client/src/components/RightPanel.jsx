import { useState } from 'react'
import { ChevronDown, ChevronUp, Info, Search, ThumbsUp, ThumbsDown, X } from 'lucide-react'

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function Section({ title, icon: Icon, defaultOpen = true, children }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border-b border-gray-100 last:border-0">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon size={14} className="text-gray-400" />
          <span className="text-xs font-semibold text-gray-600 uppercase tracking-wider">{title}</span>
        </div>
        {open
          ? <ChevronUp size={14} className="text-gray-400" />
          : <ChevronDown size={14} className="text-gray-400" />}
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  )
}

function Row({ label, value, badge }) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-xs text-gray-400">{label}</span>
      {badge
        ? <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${badge}`}>{value}</span>
        : <span className="text-xs font-medium text-gray-700">{value}</span>
      }
    </div>
  )
}

export default function RightPanel({ session, messages, feedbackStats, queryDetails, onClose }) {
  const msgCount = messages.length
  const userCount = messages.filter(m => m.role === 'user').length
  const botCount = messages.filter(m => m.role === 'bot').length

  return (
    <div className="w-[280px] h-full bg-[#f9fafb] border-l border-gray-200 flex flex-col">

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-4 border-b border-gray-200">
        <h2 className="text-sm font-semibold text-gray-800">Session Info</h2>
        <button
          onClick={onClose}
          className="lg:hidden p-1 rounded-md hover:bg-gray-200 transition-colors text-gray-400"
        >
          <X size={14} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto custom-scroll">

        {/* Session Info */}
        <Section title="Session" icon={Info} defaultOpen={true}>
          {!session ? (
            <p className="text-xs text-gray-400 italic">No active session</p>
          ) : (
            <div className="space-y-0.5">
              <Row label="Session ID" value={session.id} />
              <Row label="Created" value={formatDate(session.createdAt)} />
              <Row label="Total Messages" value={msgCount} />
              <Row label="Your Messages" value={userCount} />
              <Row label="AI Responses" value={botCount} />
            </div>
          )}
        </Section>

        {/* Query Details */}
        <Section title="Query Details" icon={Search} defaultOpen={true}>
          {!session || msgCount === 0 ? (
            <p className="text-xs text-gray-400 italic">Send a message to see details</p>
          ) : (
            <div className="space-y-0.5">
              <Row
                label="Intent"
                value={queryDetails.intent}
                badge={
                  queryDetails.intent === 'CODE'
                    ? 'bg-purple-100 text-purple-700'
                    : queryDetails.intent === 'CONVERSATION'
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-600'
                }
              />
              <Row
                label="Response Type"
                value={queryDetails.hasCode ? 'Code + Explanation' : 'Explanation'}
                badge={queryDetails.hasCode ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}
              />
              <Row
                label="Guardrails"
                value={queryDetails.isFallback ? 'Triggered' : 'Passed ✓'}
                badge={queryDetails.isFallback ? 'bg-amber-100 text-amber-700' : 'bg-green-100 text-green-700'}
              />
              <Row
                label="Attempts"
                value={queryDetails.attempts > 1 ? `${queryDetails.attempts} retries` : '1 (clean)'}
                badge={queryDetails.attempts > 1 ? 'bg-amber-100 text-amber-700' : 'bg-green-100 text-green-700'}
              />
            </div>
          )}
        </Section>

        {/* Feedback Summary */}
        <Section title="Feedback" icon={ThumbsUp} defaultOpen={true}>
          {!session || botCount === 0 ? (
            <p className="text-xs text-gray-400 italic">No responses yet</p>
          ) : (
            <div className="space-y-3">
              <div className="flex gap-3">
                <div className="flex-1 bg-green-50 border border-green-100 rounded-lg p-3 text-center">
                  <div className="flex items-center justify-center gap-1.5 mb-1">
                    <ThumbsUp size={13} className="text-green-600" />
                    <span className="text-lg font-bold text-green-600">{feedbackStats.up}</span>
                  </div>
                  <p className="text-[10px] text-green-500 font-medium">Helpful</p>
                </div>
                <div className="flex-1 bg-red-50 border border-red-100 rounded-lg p-3 text-center">
                  <div className="flex items-center justify-center gap-1.5 mb-1">
                    <ThumbsDown size={13} className="text-red-500" />
                    <span className="text-lg font-bold text-red-500">{feedbackStats.down}</span>
                  </div>
                  <p className="text-[10px] text-red-400 font-medium">Not Helpful</p>
                </div>
              </div>
              {(feedbackStats.up + feedbackStats.down) > 0 && (
                <div>
                  <div className="flex justify-between text-[10px] text-gray-400 mb-1">
                    <span>Satisfaction</span>
                    <span>{Math.round((feedbackStats.up / (feedbackStats.up + feedbackStats.down)) * 100)}%</span>
                  </div>
                  <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-green-500 rounded-full transition-all duration-500"
                      style={{ width: `${(feedbackStats.up / (feedbackStats.up + feedbackStats.down)) * 100}%` }}
                    />
                  </div>
                </div>
              )}
              <p className="text-[10px] text-gray-400">
                {botCount - feedbackStats.up - feedbackStats.down} response{botCount - feedbackStats.up - feedbackStats.down !== 1 ? 's' : ''} not yet rated
              </p>
            </div>
          )}
        </Section>
      </div>
    </div>
  )
}
