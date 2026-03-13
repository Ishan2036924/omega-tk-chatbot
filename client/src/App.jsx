/**
 * Root component — unified layout shared by welcome and chat states.
 *
 * Structure (always the same shell):
 *   • Header — title + Export button (visible on both screens)
 *   • Message area — welcome content OR chat messages, scrollable
 *   • Input bar — identical on both screens, pinned to bottom
 */
import { useState, useCallback } from 'react'
import { Share2 } from 'lucide-react'
import WelcomeScreen from './components/WelcomeScreen.jsx'
import MessageList from './components/MessageList.jsx'
import InputBar from './components/InputBar.jsx'
import { sendMessage } from './api.js'

/** Download the full conversation as a Markdown file. */
function exportConversation(messages) {
  const now = new Date()
  const dateStr = now.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
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

export default function App() {
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [hasStarted, setHasStarted] = useState(false)

  const handleSend = useCallback(
    async (text) => {
      const trimmed = text.trim()
      if (!trimmed || isLoading) return

      setMessages((prev) => [...prev, { role: 'user', text: trimmed }])
      setHasStarted(true)
      setIsLoading(true)

      // Send full history — server summarises older turns when len > 6.
      const history = messages.map((m) => {
        if (m.role === 'user') return { role: 'user', content: m.text }
        const d = m.data ?? {}
        if (d.is_fallback) return { role: 'bot', content: d.fallback_message ?? '' }
        const codeBlock = d.code ? `\n\`\`\`python\n${d.code}\n\`\`\`` : ''
        return { role: 'bot', content: `${d.explanation ?? ''}${codeBlock}` }
      })

      try {
        const data = await sendMessage(trimmed, history)
        setMessages((prev) => [...prev, { role: 'bot', data }])
      } catch (err) {
        setMessages((prev) => [
          ...prev,
          {
            role: 'bot',
            data: {
              is_fallback: true,
              fallback_message: `Connection error: ${err.message}. Is the server running?`,
              explanation: '',
              code: null,
              language: null,
            },
          },
        ])
      } finally {
        setIsLoading(false)
      }
    },
    [messages, isLoading]
  )

  return (
    <div className="h-screen flex flex-col bg-[#212121] text-white overflow-hidden">

      {/* ── Header (always visible) ── */}
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

      {/* ── Message area (welcome content OR chat messages) ── */}
      <div className="flex-1 overflow-y-auto">
        {!hasStarted ? (
          <WelcomeScreen onSend={handleSend} />
        ) : (
          <MessageList messages={messages} isLoading={isLoading} />
        )}
      </div>

      {/* ── Input bar (always at bottom) ── */}
      <div className="shrink-0 border-t border-[#2a2a2a] bg-[#212121] px-4 py-4">
        <div className="max-w-3xl mx-auto">
          <InputBar onSend={handleSend} isLoading={isLoading} />
        </div>
      </div>
    </div>
  )
}
