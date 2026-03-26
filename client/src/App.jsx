import { useState, useCallback, useEffect } from 'react'
import { supabase } from './lib/supabaseClient.js'
import AuthPage from './components/AuthPage.jsx'
import LeftPanel from './components/LeftPanel.jsx'
import MiddlePanel from './components/MiddlePanel.jsx'
import RightPanel from './components/RightPanel.jsx'
import { sendMessage, sendMessageWithFile, submitFeedback, loadHistory, loadUserSessions } from './api.js'

const genId = () => Math.random().toString(36).slice(2, 9)

/** Parse a stored bot content string back into ChatResponse-shaped data. */
function parseStoredBotContent(content) {
  const match = content.match(/^([\s\S]*?)```python\n([\s\S]*?)```/m)
  if (match) {
    return {
      explanation: match[1].trim() || 'Here is the Python code:',
      code: match[2].trim(),
      language: 'python',
      is_fallback: false,
      fallback_message: null,
      attempts: 1,
    }
  }
  return {
    explanation: content,
    code: null,
    language: null,
    is_fallback: false,
    fallback_message: null,
    attempts: 1,
  }
}

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
  // ── Auth state ───────────────────────────────────────────────────────────────
  const [user, setUser]             = useState(null)          // Supabase user object
  const [accessToken, setAccessToken] = useState(null)        // JWT for API calls
  const [authLoading, setAuthLoading] = useState(true)        // show nothing until session resolved

  // ── App state ────────────────────────────────────────────────────────────────
  const [sessions, setSessions]           = useState([])
  const [currentSessionId, setCurrentSessionId] = useState(null)
  const [isLoading, setIsLoading]         = useState(false)
  const [leftOpen, setLeftOpen]           = useState(false)
  const [rightOpen, setRightOpen]         = useState(false)
  const [view, setView]                   = useState('chat')
  const [toast, setToast]                 = useState(null)

  const currentSession = sessions.find(s => s.id === currentSessionId) ?? null
  const messages       = currentSession?.messages ?? []

  const showToast = useCallback((msg) => {
    setToast(msg)
    setTimeout(() => setToast(null), 3000)
  }, [])

  // ── Auth: resolve existing session on mount, subscribe to changes ─────────
  useEffect(() => {
    // Check if there is an existing Supabase session
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        setUser(session.user)
        setAccessToken(session.access_token)
      }
      setAuthLoading(false)
    })

    // Listen for login / logout / token refresh events
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session) {
        setUser(session.user)
        setAccessToken(session.access_token)
      } else {
        setUser(null)
        setAccessToken(null)
        setSessions([])
        setCurrentSessionId(null)
      }
    })

    return () => subscription.unsubscribe()
  }, [])

  // ── Load all past sessions from Supabase after login ─────────────────────
  useEffect(() => {
    if (!user || !accessToken) return

    loadUserSessions(accessToken).then(rows => {
      if (!rows || rows.length === 0) {
        // No history yet — open a fresh session
        const sid = genId()
        setSessions([{
          id: sid,
          title: 'Omega TK Session',
          messages: [],
          createdAt: new Date().toISOString(),
          lastActive: new Date().toISOString(),
        }])
        setCurrentSessionId(sid)
        return
      }

      // Hydrate all sessions from Supabase (messages will be loaded on demand)
      const hydrated = rows.map(r => ({
        id: r.id,
        title: r.title || 'Omega TK Session',
        messages: [],      // loaded lazily when the session is selected
        createdAt: r.created_at || new Date().toISOString(),
        lastActive: r.last_active || new Date().toISOString(),
      }))
      setSessions(hydrated)

      // Auto-select the most recent session and load its messages
      const mostRecent = hydrated[0]
      setCurrentSessionId(mostRecent.id)
      loadHistory(mostRecent.id, accessToken).then(msgRows => {
        if (!msgRows || msgRows.length === 0) return
        const msgs = msgRows.map(r => ({
          id: genId(),
          role: r.role === 'assistant' ? 'bot' : 'user',
          text: r.role !== 'assistant' ? r.content : undefined,
          data: r.role === 'assistant' ? parseStoredBotContent(r.content) : undefined,
          timestamp: r.created_at || new Date().toISOString(),
          feedback: null,
        }))
        setSessions(prev => prev.map(s =>
          s.id === mostRecent.id ? { ...s, messages: msgs } : s
        ))
        showToast(`History restored · ${msgs.length} messages`)
      }).catch(() => {})
    }).catch(() => {
      // loadUserSessions failed — start fresh
      const sid = genId()
      setSessions([{ id: sid, title: 'Omega TK Session', messages: [], createdAt: new Date().toISOString(), lastActive: new Date().toISOString() }])
      setCurrentSessionId(sid)
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, accessToken])

  // ── Select a session and lazily load its messages ─────────────────────────
  const handleSelectSession = useCallback(async (id) => {
    setCurrentSessionId(id)
    setView('chat')
    setLeftOpen(false)

    const session = sessions.find(s => s.id === id)
    if (!session || session.messages.length > 0) return   // already loaded

    try {
      const rows = await loadHistory(id, accessToken)
      if (!rows || rows.length === 0) return
      const msgs = rows.map(r => ({
        id: genId(),
        role: r.role === 'assistant' ? 'bot' : 'user',
        text: r.role !== 'assistant' ? r.content : undefined,
        data: r.role === 'assistant' ? parseStoredBotContent(r.content) : undefined,
        timestamp: r.created_at || new Date().toISOString(),
        feedback: null,
      }))
      setSessions(prev => prev.map(s => s.id === id ? { ...s, messages: msgs } : s))
    } catch {
      // silently ignore — session just stays empty
    }
  }, [sessions, accessToken])

  // ── Send a message ────────────────────────────────────────────────────────
  const handleSend = useCallback(async (text, file = null) => {
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
      setSessions(prev => [{ id: sid, title, messages: [userMsg], createdAt: new Date().toISOString(), lastActive: new Date().toISOString() }, ...prev])
      setCurrentSessionId(sid)
    } else {
      setSessions(prev => prev.map(s => {
        if (s.id !== sid) return s
        const newTitle = s.messages.length === 0
          ? (trimmed.length > 42 ? trimmed.slice(0, 42) + '…' : trimmed)
          : s.title
        return { ...s, title: newTitle, messages: [...s.messages, userMsg], lastActive: new Date().toISOString() }
      }))
    }

    setIsLoading(true)
    try {
      const data = file
        ? await sendMessageWithFile(trimmed, history, sid, file, accessToken)
        : await sendMessage(trimmed, history, sid, accessToken)
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
  }, [currentSessionId, messages, isLoading, accessToken])

  // ── Feedback (thumbs up/down) ─────────────────────────────────────────────
  const handleFeedback = useCallback((msgId, type) => {
    setSessions(prev => prev.map(s =>
      s.id === currentSessionId
        ? { ...s, messages: s.messages.map(m => m.id === msgId ? { ...m, feedback: m.feedback === type ? null : type } : m) }
        : s
    ))
    submitFeedback(currentSessionId, msgId, type, accessToken)
  }, [currentSessionId, accessToken])

  // ── Export ────────────────────────────────────────────────────────────────
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

  // ── New chat ──────────────────────────────────────────────────────────────
  const handleNewChat = useCallback(() => {
    const sid = genId()
    setCurrentSessionId(sid)
    setSessions(prev => [{
      id: sid, title: 'Omega TK Session', messages: [],
      createdAt: new Date().toISOString(), lastActive: new Date().toISOString(),
    }, ...prev])
    setView('chat')
    setLeftOpen(false)
  }, [])

  // ── Logout ────────────────────────────────────────────────────────────────
  const handleLogout = useCallback(async () => {
    await supabase.auth.signOut()
    // onAuthStateChange will clear user + accessToken + sessions
  }, [])

  // ── Right panel data ──────────────────────────────────────────────────────
  const lastBot = messages.filter(m => m.role === 'bot').at(-1)
  const queryDetails = {
    isFallback: lastBot?.data?.is_fallback ?? false,
    attempts:   lastBot?.data?.attempts ?? 1,
    hasCode:    !!(lastBot?.data?.code),
    intent:     lastBot?.data?.code ? 'CODE' : lastBot ? 'CONVERSATION' : '—',
  }
  const feedbackStats = {
    up:   messages.filter(m => m.feedback === 'up').length,
    down: messages.filter(m => m.feedback === 'down').length,
  }

  // ── Render ────────────────────────────────────────────────────────────────

  // While Supabase resolves the existing session, show nothing (avoids flash)
  if (authLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-sidebar">
        <div className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
      </div>
    )
  }

  // Not authenticated — show full-screen login / signup
  if (!user) {
    return <AuthPage onLogin={setUser} />
  }

  // Authenticated — show the main three-panel layout
  return (
    <div className="flex h-screen overflow-hidden bg-gray-100 font-sans">

      {/* Mobile overlay backdrop */}
      {(leftOpen || rightOpen) && (
        <div
          className="fixed inset-0 bg-black/40 z-20 lg:hidden"
          onClick={() => { setLeftOpen(false); setRightOpen(false) }}
        />
      )}

      {/* Toast notification */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-gray-800 text-white text-xs px-4 py-2 rounded-full shadow-lg pointer-events-none">
          {toast}
        </div>
      )}

      {/* ── Left Panel ─────────────────────────────────── */}
      <div className={`
        fixed lg:relative z-30 lg:z-auto h-full panel-slide
        ${leftOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
        <LeftPanel
          sessions={sessions}
          currentSessionId={currentSessionId}
          onSelectSession={handleSelectSession}
          onNewChat={handleNewChat}
          activeView={view}
          onSelectView={setView}
          user={user}
          onLogout={handleLogout}
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
          view={view}
          sessionId={currentSessionId}
          accessToken={accessToken}
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
