import { useState, useCallback, useEffect, useRef, useMemo } from 'react'
import { supabase } from './lib/supabaseClient.js'
import AuthPage from './components/AuthPage.jsx'
import LeftPanel from './components/LeftPanel.jsx'
import MiddlePanel from './components/MiddlePanel.jsx'
import RightPanel from './components/RightPanel.jsx'
import { sendMessage, sendMessageWithFile, submitFeedback, loadHistory, loadUserSessions } from './api.js'

// ── Constants ─────────────────────────────────────────────────────────────────

const LS_KEY = 'omega_session_id'
const genId  = () => Math.random().toString(36).slice(2, 9)

// ── Helpers ───────────────────────────────────────────────────────────────────

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

/** Build a markdown export string from a session + its messages. */
function buildExportMarkdown(session, msgs) {
  const date = new Date(session.createdAt).toLocaleDateString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric'
  })
  let md = `# Omega TK Code Assistant — Chat Export\n\n**Date**: ${date}\n**Session**: ${session.id}\n\n---\n\n`
  for (const msg of msgs) {
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

/** Hydrate message rows from Supabase into local message objects. */
function hydrateMessages(rows) {
  return rows.map(r => ({
    id: genId(),
    role: r.role === 'assistant' ? 'bot' : 'user',
    text: r.role !== 'assistant' ? r.content : undefined,
    data: r.role === 'assistant' ? parseStoredBotContent(r.content) : undefined,
    timestamp: r.created_at || new Date().toISOString(),
    feedback: null,
  }))
}

// ── App ───────────────────────────────────────────────────────────────────────

export default function App() {
  // ── Auth state ──────────────────────────────────────────────────────────────
  const [user, setUser]               = useState(null)
  const [accessToken, setAccessToken] = useState(null)
  const [authLoading, setAuthLoading] = useState(true)   // true until ALL init steps done

  // ── Session metadata (title, timestamps) — NO messages stored here ──────────
  // This is the ground truth for the left panel session list.
  const [sessions, setSessions]               = useState([])
  const [currentSessionId, setCurrentSessionId] = useState(null)

  // ── Message store — the ONLY place messages live ────────────────────────────
  // { [sessionId]: Message[] }
  // Completely decoupled from session metadata so:
  //   • setSessions (title updates, new session, metadata) can NEVER wipe messages
  //   • responses are routed by the sessionId captured at send-time, not at arrival-time
  const [messagesMap, setMessagesMap] = useState({})

  // ── Other UI state ──────────────────────────────────────────────────────────
  const [isLoading, setIsLoading]   = useState(false)
  const [leftOpen, setLeftOpen]     = useState(false)
  const [rightOpen, setRightOpen]   = useState(false)
  const [view, setView]             = useState('chat')
  const [toast, setToast]           = useState(null)

  // Prevents onAuthStateChange(INITIAL_SESSION) from doubling up on getSession()
  const hasInitialized = useRef(false)

  // Tracks the currently-logged-in user ID so onAuthStateChange(SIGNED_IN) can
  // distinguish "fresh login" from "silent token refresh on tab focus".
  // Using a ref (not state) so the async onAuthStateChange closure always reads
  // the latest value without needing to be recreated.
  const currentUserIdRef = useRef(null)

  // ── Derived ─────────────────────────────────────────────────────────────────

  // Fast message lookup for the active session
  const messages = messagesMap[currentSessionId] ?? []

  // Thin view that merges metadata + messages — consumed by LeftPanel (count display)
  // and by handleExport. Uses useMemo so downstream only re-renders when either
  // sessions metadata OR the relevant messages slice actually changes.
  const sessionsWithMessages = useMemo(
    () => sessions.map(s => ({ ...s, messages: messagesMap[s.id] ?? [] })),
    [sessions, messagesMap]
  )

  const currentSession = sessionsWithMessages.find(s => s.id === currentSessionId) ?? null

  // ── Toast ───────────────────────────────────────────────────────────────────
  const showToast = useCallback((msg) => {
    setToast(msg)
    setTimeout(() => setToast(null), 3000)
  }, [])

  // ── Core restore: given a valid token, load all sessions + history ──────────
  const restoreForToken = useCallback(async (token) => {
    console.log('[Restore] Loading sessions from API…')
    let rows = []
    try { rows = await loadUserSessions(token) } catch { /* ok */ }
    console.log('[Restore] API returned', rows?.length ?? 0, 'session(s)')

    if (!rows || rows.length === 0) {
      // First-time user — create a fresh session
      const sid = localStorage.getItem(LS_KEY) || genId()
      localStorage.setItem(LS_KEY, sid)
      console.log('[Restore] No sessions on server — new session:', sid)
      setSessions([{
        id: sid, title: 'Omega TK Session',
        createdAt: new Date().toISOString(), lastActive: new Date().toISOString(),
      }])
      setMessagesMap({ [sid]: [] })
      setCurrentSessionId(sid)
      return
    }

    // Hydrate session metadata list (messages loaded lazily per-session)
    const hydrated = rows.map(r => ({
      id: r.id,
      title: r.title || 'Omega TK Session',
      createdAt: r.created_at || new Date().toISOString(),
      lastActive: r.last_active || new Date().toISOString(),
    }))
    setSessions(hydrated)
    setMessagesMap({})   // clear all cached messages on full restore

    // Pick which session to open: prefer the one from localStorage
    const stored   = localStorage.getItem(LS_KEY)
    const targetId = (stored && hydrated.find(s => s.id === stored))
      ? stored
      : hydrated[0].id
    console.log('[Restore] localStorage had:', stored, '→ opening session:', targetId)
    setCurrentSessionId(targetId)
    localStorage.setItem(LS_KEY, targetId)

    // Load history for the selected session
    try {
      console.log('[Restore] Loading history for session:', targetId)
      const msgRows = await loadHistory(targetId, token)
      console.log('[Restore] History rows received:', msgRows?.length ?? 0)
      if (msgRows && msgRows.length > 0) {
        const msgs = hydrateMessages(msgRows)
        setMessagesMap(prev => ({ ...prev, [targetId]: msgs }))
        showToast(`History restored · ${msgs.length} messages`)
      }
    } catch { /* silently ignore */ }
  }, [showToast])

  // ── Single-effect sequential auth init ─────────────────────────────────────
  useEffect(() => {
    let cancelled = false

    async function initialize() {
      // Step 1: resolve any existing Supabase session
      const { data: { session } } = await supabase.auth.getSession()

      if (cancelled) return

      if (!session) {
        console.log('[Auth] No existing session — showing login page')
        hasInitialized.current = true
        setAuthLoading(false)
        return
      }

      console.log('[Auth] Existing session found for', session.user.email)

      // Step 2: set auth state + track user ID in ref
      setUser(session.user)
      setAccessToken(session.access_token)
      currentUserIdRef.current = session.user.id

      // Steps 3-6: restore sessions, pick session, load history
      console.log('[Auth] Restoring sessions and history…')
      await restoreForToken(session.access_token)
      console.log('[Auth] Restore complete — rendering UI')

      if (!cancelled) {
        hasInitialized.current = true
        setAuthLoading(false)
      }
    }

    initialize()

    // Subscribe to future auth events — SKIP the INITIAL_SESSION echo
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        if (!hasInitialized.current) return  // still initialising — ignore echo

        if (event === 'SIGNED_IN' && session) {
          const isFreshLogin = currentUserIdRef.current !== session.user.id
          console.log(
            '[Auth] SIGNED_IN event — isFreshLogin:', isFreshLogin,
            '(currentUserIdRef:', currentUserIdRef.current,
            '→ new:', session.user.id, ')'
          )

          // Always update user + token
          setUser(session.user)
          setAccessToken(session.access_token)
          currentUserIdRef.current = session.user.id

          if (isFreshLogin) {
            // Genuine login (user was null or different) — run full restore
            console.log('[Auth] Fresh login detected — restoring sessions and history')
            await restoreForToken(session.access_token)
          } else {
            // Same user, token refresh (e.g., tab focus after ~1h) — do NOT
            // wipe session state; just updating accessToken above is enough.
            console.log('[Auth] Token refresh for same user — skipping re-init')
          }
        } else if (event === 'SIGNED_OUT') {
          console.log('[Auth] SIGNED_OUT — clearing all state')
          setUser(null)
          setAccessToken(null)
          setSessions([])
          setMessagesMap({})
          setCurrentSessionId(null)
          currentUserIdRef.current = null
          localStorage.removeItem(LS_KEY)
        } else if (event === 'TOKEN_REFRESHED' && session) {
          console.log('[Auth] TOKEN_REFRESHED — updating access token only')
          setAccessToken(session.access_token)
        }
      }
    )

    return () => {
      cancelled = true
      subscription.unsubscribe()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Select a session — reload messages from server on every explicit switch ──
  const handleSelectSession = useCallback(async (id) => {
    console.log('[Session] Switching to session:', id)

    // 1. Clear the target session's messages immediately so the user sees a
    //    clean slate rather than stale data from a previous visit.
    setMessagesMap(prev => ({ ...prev, [id]: [] }))

    // 2. Update session pointer + localStorage before any async work.
    setCurrentSessionId(id)
    setView('chat')
    setLeftOpen(false)
    localStorage.setItem(LS_KEY, id)

    // 3. Always reload from server — ensures fresh, authoritative history.
    try {
      const rows = await loadHistory(id, accessToken)
      console.log('[Session] Loaded', rows?.length ?? 0, 'messages for session:', id)
      if (!rows || rows.length === 0) return
      const msgs = hydrateMessages(rows)
      // Write into the map keyed by the target session — regardless of what
      // currentSessionId is NOW (user might have switched again during fetch).
      setMessagesMap(prev => ({ ...prev, [id]: msgs }))
    } catch {
      // silently ignore — session stays empty
    }
  }, [accessToken])

  // ── Send a message ──────────────────────────────────────────────────────────
  const handleSend = useCallback(async (text, file = null) => {
    const trimmed = text.trim()
    if (!trimmed || isLoading) return

    // ★ Capture the session ID RIGHT NOW, before any async work.
    //   All state mutations below use this captured value so the response
    //   always lands in the session that was active when the user pressed Send,
    //   regardless of session switches that happen while the request is in-flight.
    const sidAtSendTime = currentSessionId

    // Build conversation history for the backend (last 6 turns)
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

    // ── Create or update session metadata ──────────────────────────────────
    let sid = sidAtSendTime
    if (!sid) {
      // No active session yet — create one now
      sid = genId()
      localStorage.setItem(LS_KEY, sid)
      const title = trimmed.length > 42 ? trimmed.slice(0, 42) + '…' : trimmed
      setSessions(prev => [{
        id: sid, title,
        createdAt: new Date().toISOString(), lastActive: new Date().toISOString(),
      }, ...prev])
      setCurrentSessionId(sid)
    } else {
      // Update title on first message; always bump lastActive
      const isFirstMessage = messages.length === 0
      const newTitle = isFirstMessage
        ? (trimmed.length > 42 ? trimmed.slice(0, 42) + '…' : trimmed)
        : undefined   // undefined → keep existing title
      setSessions(prev => prev.map(s => {
        if (s.id !== sid) return s
        return {
          ...s,
          ...(newTitle ? { title: newTitle } : {}),
          lastActive: new Date().toISOString(),
        }
      }))
    }

    // ── Append user message to the CORRECT session's message list ──────────
    setMessagesMap(prev => ({
      ...prev,
      [sid]: [...(prev[sid] ?? []), userMsg],
    }))

    // ── Fire the API request ────────────────────────────────────────────────
    setIsLoading(true)
    try {
      const data = file
        ? await sendMessageWithFile(trimmed, history, sid, file, accessToken)
        : await sendMessage(trimmed, history, sid, accessToken)

      const botMsg = {
        id: genId(), role: 'bot', data,
        timestamp: new Date().toISOString(), feedback: null,
      }

      // ★ Route response to the session captured at send-time — NOT to
      //   whatever currentSessionId is right now.
      setMessagesMap(prev => ({
        ...prev,
        [sid]: [...(prev[sid] ?? []), botMsg],
      }))

      // Bump lastActive in metadata
      setSessions(prev => prev.map(s =>
        s.id === sid ? { ...s, lastActive: new Date().toISOString() } : s
      ))
    } catch (err) {
      const botMsg = {
        id: genId(), role: 'bot',
        data: { is_fallback: true, fallback_message: `Connection error: ${err.message}` },
        timestamp: new Date().toISOString(), feedback: null,
      }
      setMessagesMap(prev => ({
        ...prev,
        [sid]: [...(prev[sid] ?? []), botMsg],
      }))
    } finally {
      setIsLoading(false)
    }
  }, [currentSessionId, messages, isLoading, accessToken])

  // ── Feedback ────────────────────────────────────────────────────────────────
  const handleFeedback = useCallback((msgId, type) => {
    setMessagesMap(prev => ({
      ...prev,
      [currentSessionId]: (prev[currentSessionId] ?? []).map(m =>
        m.id === msgId ? { ...m, feedback: m.feedback === type ? null : type } : m
      ),
    }))
    submitFeedback(currentSessionId, msgId, type, accessToken)
  }, [currentSessionId, accessToken])

  // ── Export ──────────────────────────────────────────────────────────────────
  const handleExport = useCallback(() => {
    if (!currentSession) return
    const md = buildExportMarkdown(currentSession, messages)
    const blob = new Blob([md], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `omega-tk-${currentSession.id}.md`
    a.click()
    URL.revokeObjectURL(url)
  }, [currentSession, messages])

  // ── New chat ────────────────────────────────────────────────────────────────
  const handleNewChat = useCallback(() => {
    const sid = genId()
    localStorage.setItem(LS_KEY, sid)
    setCurrentSessionId(sid)
    setSessions(prev => [{
      id: sid, title: 'Omega TK Session',
      createdAt: new Date().toISOString(), lastActive: new Date().toISOString(),
    }, ...prev])
    setMessagesMap(prev => ({ ...prev, [sid]: [] }))
    setView('chat')
    setLeftOpen(false)
  }, [])

  // ── Logout ──────────────────────────────────────────────────────────────────
  const handleLogout = useCallback(async () => {
    await supabase.auth.signOut()
    // onAuthStateChange(SIGNED_OUT) clears all state + localStorage
  }, [])

  // ── Right panel derived data ────────────────────────────────────────────────
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

  // ── Render ──────────────────────────────────────────────────────────────────

  // Block until we've finished resolving the session (avoids flash + race)
  if (authLoading) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-3 bg-sidebar">
        <div className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
        <p className="text-white/40 text-xs">Restoring your session…</p>
      </div>
    )
  }

  // Not authenticated — show full-screen login / signup
  if (!user) {
    return (
      <AuthPage
        onLogin={(usr, tok) => {
          // Set both user + token atomically so the main layout
          // never renders with a null accessToken.
          console.log('[Auth] AuthPage onLogin — user:', usr?.email, 'hasToken:', !!tok)
          if (tok) setAccessToken(tok)
          setUser(usr)
        }}
      />
    )
  }

  // Authenticated — three-panel layout
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

      {/* ── Left Panel ──────────────────────────────────────── */}
      <div className={`
        fixed lg:relative z-30 lg:z-auto h-full panel-slide
        ${leftOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
        <LeftPanel
          sessions={sessionsWithMessages}
          currentSessionId={currentSessionId}
          onSelectSession={handleSelectSession}
          onNewChat={handleNewChat}
          activeView={view}
          onSelectView={setView}
          user={user}
          onLogout={handleLogout}
        />
      </div>

      {/* ── Middle Panel ────────────────────────────────────── */}
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

      {/* ── Right Panel ─────────────────────────────────────── */}
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
