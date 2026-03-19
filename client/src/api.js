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
