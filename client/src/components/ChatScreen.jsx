/**
 * Active chat screen — full-height flex layout with:
 *   • A slim header with app title + Export conversation button
 *   • Scrollable message area (flex-1)
 *   • Sticky input bar (shrink-0) pinned to the bottom
 */
import { Share2 } from 'lucide-react'
import MessageList from './MessageList.jsx'
import InputBar from './InputBar.jsx'

/**
 * Export the full conversation as a Markdown file and trigger a download.
 * @param {Array} messages
 */
function exportConversation(messages) {
  const now = new Date()
  const dateStr = now.toLocaleDateString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric',
  })
  const timestamp = now.toISOString().replace(/[:.]/g, '-').slice(0, 19)

  let md = `# Omega TK Code Assistant — Chat Export\n\n**Date**: ${dateStr}\n\n---\n\n`

  for (const msg of messages) {
    if (msg.role === 'user') {
      md += `**User**: ${msg.text}\n\n`
    } else {
      const d = msg.data ?? {}
      if (d.is_fallback) {
        md += `**Assistant**: ⚠ ${d.fallback_message ?? ''}\n\n`
      } else {
        if (d.explanation) md += `**Assistant**: ${d.explanation}\n\n`
        if (d.code) md += `\`\`\`python\n${d.code}\n\`\`\`\n\n`
      }
    }
  }

  const blob = new Blob([md], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `omega-tk-chat-${timestamp}.md`
  a.click()
  URL.revokeObjectURL(url)
}

/**
 * @param {{
 *   messages: Array,
 *   isLoading: boolean,
 *   onSend: (text: string) => void
 * }} props
 */
export default function ChatScreen({ messages, isLoading, onSend }) {
  return (
    <div className="flex flex-col h-full">

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="shrink-0 flex items-center justify-between px-4 py-2.5 border-b border-[#2a2a2a]">
        <span className="text-sm text-gray-500 font-medium tracking-wide">
          Omega TK Code Assistant
        </span>
        <button
          onClick={() => exportConversation(messages)}
          disabled={messages.length === 0}
          aria-label="Export conversation as Markdown"
          title="Export as Markdown"
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-[#2f2f2f] transition-colors text-xs disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <Share2 size={13} />
          <span>Export</span>
        </button>
      </div>

      {/* ── Scrollable message area ──────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto">
        <MessageList messages={messages} isLoading={isLoading} />
      </div>

      {/* ── Sticky input bar ────────────────────────────────────────────── */}
      <div className="shrink-0 border-t border-[#2a2a2a] bg-[#212121] px-4 py-4">
        <div className="max-w-3xl mx-auto">
          <InputBar onSend={onSend} isLoading={isLoading} />
        </div>
      </div>
    </div>
  )
}
