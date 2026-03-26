/**
 * API client — thin wrapper around the FastAPI /api/* endpoints.
 *
 * Every function that talks to a protected route accepts an optional
 * `token` parameter (the Supabase JWT access_token from the session).
 * When provided it is forwarded as `Authorization: Bearer <token>`.
 *
 * In dev mode, Vite proxies /api → localhost:8000.
 * In prod mode, FastAPI serves everything on :8000.
 */

const BASE_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

/** Build common JSON headers, optionally with a Bearer token. */
function jsonHeaders(token) {
  const h = { 'Content-Type': 'application/json' }
  if (token) h['Authorization'] = `Bearer ${token}`
  return h
}

/** Attach a Bearer token to a plain Headers or object, if present. */
function withAuth(headers = {}, token) {
  if (token) return { ...headers, Authorization: `Bearer ${token}` }
  return headers
}

// ── Chat ──────────────────────────────────────────────────────────────────────

/**
 * Send a message to the RAG chatbot.
 *
 * @param {string}  message
 * @param {Array}   history
 * @param {string|null} sessionId
 * @param {string|null} token     — Supabase JWT access token
 */
export async function sendMessage(message, history = [], sessionId = null, token = null) {
  const body = { message, history }
  if (sessionId) body.session_id = sessionId

  const response = await fetch(`${BASE_URL}/api/chat`, {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try { const err = await response.json(); detail = err.detail || detail } catch {}
    throw new Error(detail)
  }
  return response.json()
}

/**
 * Send a message with an optional file attachment (multipart).
 */
export async function sendMessageWithFile(message, history = [], sessionId = null, file = null, token = null) {
  const formData = new FormData()
  formData.append('message', message)
  formData.append('history_json', JSON.stringify(history))
  if (sessionId) formData.append('session_id', sessionId)
  if (file) formData.append('file', file)

  const res = await fetch(`${BASE_URL}/api/chat-file`, {
    method: 'POST',
    headers: withAuth({}, token),   // no Content-Type — browser sets multipart boundary
    body: formData,
  })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try { const e = await res.json(); detail = e.detail || detail } catch {}
    throw new Error(detail)
  }
  return res.json()
}

// ── Feedback ──────────────────────────────────────────────────────────────────

/**
 * Submit thumbs-up / thumbs-down feedback. Fire-and-forget.
 */
export async function submitFeedback(sessionId, messageId, feedback, token = null) {
  try {
    await fetch(`${BASE_URL}/api/feedback`, {
      method: 'POST',
      headers: jsonHeaders(token),
      body: JSON.stringify({ session_id: sessionId, message_id: messageId, feedback }),
    })
  } catch {
    // fire-and-forget — never surface feedback errors to the user
  }
}

// ── Analytics ─────────────────────────────────────────────────────────────────

/**
 * Fetch analytics data (last 24 h query stats). Public — no token needed.
 */
export async function fetchAnalytics(token = null) {
  const res = await fetch(`${BASE_URL}/api/analytics`, { headers: withAuth({}, token) })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// ── Transcription ─────────────────────────────────────────────────────────────

/**
 * Send an audio blob to Whisper and return the transcribed text.
 */
export async function transcribeAudio(blob, token = null) {
  const formData = new FormData()
  formData.append('audio', blob, 'recording.webm')
  const res = await fetch(`${BASE_URL}/api/transcribe`, {
    method: 'POST',
    headers: withAuth({}, token),
    body: formData,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// ── History ───────────────────────────────────────────────────────────────────

/**
 * Load chat history for a session from Supabase.
 * When a token is provided, the backend enforces user ownership.
 *
 * @param {string} sessionId
 * @param {string|null} token
 */
export async function loadHistory(sessionId, token = null) {
  try {
    const res = await fetch(`${BASE_URL}/api/history/${encodeURIComponent(sessionId)}`, {
      headers: withAuth({}, token),
    })
    if (!res.ok) return []
    return res.json()
  } catch {
    return []
  }
}

/**
 * Load all past sessions for the authenticated user.
 * Returns [] if not authenticated or on error.
 *
 * @param {string} token — Supabase JWT access token (required)
 */
export async function loadUserSessions(token) {
  if (!token) return []
  try {
    const res = await fetch(`${BASE_URL}/api/sessions`, {
      headers: withAuth({}, token),
    })
    if (!res.ok) return []
    return res.json()
  } catch {
    return []
  }
}

// ── Knowledge base ────────────────────────────────────────────────────────────

/**
 * Load ALL knowledge sources for the authenticated user across every session.
 * Uses the dedicated /api/knowledge/me endpoint — no session_id needed.
 * Called during app initialisation so sources are available immediately.
 *
 * @param {string} token — Supabase JWT access token (required)
 * @returns {Promise<Array>}
 */
export async function loadMyKnowledge(token) {
  if (!token) return []
  try {
    const res = await fetch(`${BASE_URL}/api/knowledge/me`, {
      headers: withAuth({}, token),
    })
    if (!res.ok) return []
    return res.json()
  } catch {
    return []
  }
}

/**
 * Add pasted text to the knowledge base.
 */
export async function addKnowledge(text, source, sessionId, token = null) {
  const formData = new FormData()
  formData.append('text', text)
  formData.append('source', source)
  formData.append('session_id', sessionId)
  const res = await fetch(`${BASE_URL}/api/knowledge`, {
    method: 'POST',
    headers: withAuth({}, token),
    body: formData,
  })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try { const e = await res.json(); detail = e.detail || detail } catch {}
    throw new Error(detail)
  }
  return res.json()
}

/**
 * Upload a file to the knowledge base.
 */
export async function addKnowledgeFile(file, sessionId, token = null) {
  const formData = new FormData()
  formData.append('session_id', sessionId)
  formData.append('file', file)
  const res = await fetch(`${BASE_URL}/api/knowledge-file`, {
    method: 'POST',
    headers: withAuth({}, token),
    body: formData,
  })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try { const e = await res.json(); detail = e.detail || detail } catch {}
    throw new Error(detail)
  }
  return res.json()
}

/**
 * List knowledge sources.
 * When authenticated, returns user-scoped sources (cross-session).
 */
export async function listKnowledge(sessionId, token = null) {
  try {
    const res = await fetch(`${BASE_URL}/api/knowledge/${encodeURIComponent(sessionId)}`, {
      headers: withAuth({}, token),
    })
    if (!res.ok) return []
    return res.json()
  } catch {
    return []
  }
}

/**
 * Delete a knowledge source by chunk ID.
 */
export async function deleteKnowledge(chunkId, token = null) {
  const res = await fetch(`${BASE_URL}/api/knowledge/${chunkId}`, {
    method: 'DELETE',
    headers: withAuth({}, token),
  })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try { const e = await res.json(); detail = e.detail || detail } catch {}
    throw new Error(detail)
  }
  return res.json()
}
