/**
 * API client — thin wrapper around the FastAPI /api/chat endpoint.
 * In dev mode, Vite proxies /api → localhost:8000.
 * In prod mode, FastAPI serves everything on :8000.
 */

const BASE_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

/**
 * Send a message to the RAG chatbot.
 *
 * @param {string} message
 * @param {Array<{role: string, content: string}>} history
 * @param {string|null} sessionId  — forwarded to backend for Supabase logging
 */
export async function sendMessage(message, history = [], sessionId = null) {
  const body = { message, history }
  if (sessionId) body.session_id = sessionId

  const response = await fetch(`${BASE_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const err = await response.json()
      detail = err.detail || detail
    } catch {
      // ignore parse errors on error responses
    }
    throw new Error(detail)
  }

  return response.json()
}

/**
 * Submit thumbs-up / thumbs-down feedback for a bot response.
 * Fire-and-forget — errors are silently swallowed.
 *
 * @param {string} sessionId
 * @param {string} messageId
 * @param {'up'|'down'} feedback
 */
export async function submitFeedback(sessionId, messageId, feedback) {
  try {
    await fetch(`${BASE_URL}/api/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, message_id: messageId, feedback }),
    })
  } catch {
    // fire-and-forget — never surface feedback errors to the user
  }
}

/**
 * Fetch analytics data (last 24 h query stats).
 */
export async function fetchAnalytics() {
  const res = await fetch(`${BASE_URL}/api/analytics`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

/**
 * Send an audio blob to Whisper and return the transcribed text.
 * @param {Blob} blob — raw audio from MediaRecorder
 * @returns {Promise<{text: string}>}
 */
export async function transcribeAudio(blob) {
  const formData = new FormData()
  formData.append('audio', blob, 'recording.webm')
  const res = await fetch(`${BASE_URL}/api/transcribe`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

/**
 * Send a message with an optional file attachment (multipart).
 * @param {string} message
 * @param {Array} history
 * @param {string|null} sessionId
 * @param {File|null} file
 */
export async function sendMessageWithFile(message, history = [], sessionId = null, file = null) {
  const formData = new FormData()
  formData.append('message', message)
  formData.append('history_json', JSON.stringify(history))
  if (sessionId) formData.append('session_id', sessionId)
  if (file) formData.append('file', file)

  const res = await fetch(`${BASE_URL}/api/chat-file`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try { const e = await res.json(); detail = e.detail || detail } catch {}
    throw new Error(detail)
  }
  return res.json()
}
