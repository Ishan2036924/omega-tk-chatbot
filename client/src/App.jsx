import { useState, useCallback } from 'react'
import LeftPanel from './components/LeftPanel.jsx'
import MiddlePanel from './components/MiddlePanel.jsx'
import RightPanel from './components/RightPanel.jsx'
import { sendMessage, submitFeedback } from './api.js'

const genId = () => Math.random().toString(36).slice(2, 9)

function buildExportMarkdown(session) {
  const date = new Date(session.createdAt).toLocaleDateString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric'
  })
  let md = `# Omega TK Code Assistant — Chat Export\n\n**Date**: ${date}\n**Session**: ${session.id}\n\n---\n\n`
  for (const msg of session.messages) {
    if (msg.role === 'user') {
      md += `**You**: ${msg.text}\n\n`
    } else {
      const d = msg.data ?? {}
      if (d.is_fallback) md += `**Omega TK**: ⚠ ${d.fallback_message ?? ''}\n\n`
      else {
        if (d.explanation) md += `**Omega TK**: ${d.explanation}\n\n`
        if (d.code) md += `\`\`\`${d.language || 'python'}\n${d.code}\n\`\`\`\n\n`
      }
    }
  }
  return md
}

export default function App() {
  const [sessions, setSessions] = useState([])
  const [currentSessionId, setCurrentSessionId] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [leftOpen, setLeftOpen] = useState(false)   // mobile overlay
  const [rightOpen, setRightOpen] = useState(false) // mobile overlay

  const currentSession = sessions.find(s => s.id === currentSessionId) ?? null
  const messages = currentSession?.messages ?? []

  /* ── Send a message ─────────────────────────────────── */
  const handleSend = useCallback(async (text) => {
    const trimmed = text.trim()
    if (!trimmed || isLoading) return

    // Build history for backend (last 6 turns)
    const history = messages.slice(-6).map(m => {
      if (m.role === 'user') return { role: 'user', content: m.text }
      const d = m.data ?? {}
      if (d.is_fallback) return { role: 'bot', content: d.fallback_message ?? '' }
      const code = d.code ? `\n\`\`\`${d.language || 'python'}\n${d.code}\n\`\`\`` : ''
      return { role: 'bot', content: `${d.explanation ?? ''}${code}` }
    })

    const userMsg = {
      id: genId(), role: 'user', text: trimmed,
      timestamp: new Date().toISOString(), feedback: null,
    }

    // Create or update session
    let sid = currentSessionId
    if (!sid) {
      sid = genId()
      const title = trimmed.length > 42 ? trimmed.slice(0, 42) + '…' : trimmed
      setSessions(prev => [{
        id: sid, title, messages: [userMsg],
        createdAt: new Date().toISOString(), lastActive: new Date().toISOString(),
      }, ...prev])
      setCurrentSessionId(sid)
    } else {
      setSessions(prev => prev.map(s =>
        s.id === sid
          ? { ...s, messages: [...s.messages, userMsg], lastActive: new Date().toISOString() }
          : s
      ))
    }

    setIsLoading(true)
    try {
      const data = await sendMessage(trimmed, history, sid)
      const botMsg = { id: genId(), role: 'bot', data, timestamp: new Date().toISOString(), feedback: null }
      setSessions(prev => prev.map(s =>
        s.id === sid ? { ...s, messages: [...s.messages, botMsg], lastActive: new Date().toISOString() } : s
      ))
    } catch (err) {
      const botMsg = {
        id: genId(), role: 'bot',
        data: { is_fallback: true, fallback_message: `Connection error: ${err.message}` },
        timestamp: new Date().toISOString(), feedback: null,
      }
      setSessions(prev => prev.map(s =>
        s.id === sid ? { ...s, messages: [...s.messages, botMsg] } : s
      ))
    } finally {
      setIsLoading(false)
    }
  }, [currentSessionId, messages, isLoading])

  /* ── Feedback (thumbs up/down) ───────────────────────── */
  const handleFeedback = useCallback((msgId, type) => {
    setSessions(prev => prev.map(s =>
      s.id === currentSessionId
        ? {
            ...s,
            messages: s.messages.map(m =>
              m.id === msgId ? { ...m, feedback: m.feedback === type ? null : type } : m
            ),
          }
        : s
    ))
    submitFeedback(currentSessionId, msgId, type)
  }, [currentSessionId])

  /* ── Export ──────────────────────────────────────────── */
  const handleExport = useCallback(() => {
    if (!currentSession) return
    const md = buildExportMarkdown(currentSession)
    const blob = new Blob([md], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `omega-tk-${currentSession.id}.md`
    a.click()
    URL.revokeObjectURL(url)
  }, [currentSession])

  /* ── Right panel data ────────────────────────────────── */
  const lastBot = messages.filter(m => m.role === 'bot').at(-1)
  const queryDetails = {
    isFallback: lastBot?.data?.is_fallback ?? false,
    attempts: lastBot?.data?.attempts ?? 1,
    hasCode: !!(lastBot?.data?.code),
    intent: lastBot?.data?.code ? 'CODE' : lastBot ? 'CONVERSATION' : '—',
  }
  const feedbackStats = {
    up: messages.filter(m => m.feedback === 'up').length,
    down: messages.filter(m => m.feedback === 'down').length,
  }

  return (
    <div className="flex h-screen overflow-hidden bg-gray-100 font-sans">

      {/* Mobile overlay backdrop */}
      {(leftOpen || rightOpen) && (
        <div
          className="fixed inset-0 bg-black/40 z-20 lg:hidden"
          onClick={() => { setLeftOpen(false); setRightOpen(false) }}
        />
      )}

      {/* ── Left Panel ─────────────────────────────────── */}
      <div className={`
        fixed lg:relative z-30 lg:z-auto h-full panel-slide
        ${leftOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
        <LeftPanel
          sessions={sessions}
          currentSessionId={currentSessionId}
          onSelectSession={(id) => { setCurrentSessionId(id); setLeftOpen(false) }}
          onNewChat={() => { setCurrentSessionId(null); setLeftOpen(false) }}
        />
      </div>

      {/* ── Middle Panel ───────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 h-full">
        <MiddlePanel
          session={currentSession}
          messages={messages}
          isLoading={isLoading}
          onSend={handleSend}
          onFeedback={handleFeedback}
          onExport={handleExport}
          onToggleLeft={() => setLeftOpen(true)}
          onToggleRight={() => setRightOpen(true)}
        />
      </div>

      {/* ── Right Panel ────────────────────────────────── */}
      <div className={`
        fixed right-0 lg:relative z-30 lg:z-auto h-full panel-slide
        ${rightOpen ? 'translate-x-0' : 'translate-x-full lg:translate-x-0'}
      `}>
        <RightPanel
          session={currentSession}
          messages={messages}
          feedbackStats={feedbackStats}
          queryDetails={queryDetails}
          onClose={() => setRightOpen(false)}
        />
      </div>
    </div>
  )
}
