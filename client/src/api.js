/**
 * API client — thin wrapper around the FastAPI /api/chat endpoint.
 * In dev mode, Vite proxies /api → localhost:8000.
 * In prod mode, FastAPI serves everything on :8000.
 */

const BASE_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

/**
 * Send a message to the RAG chatbot.
 *
 * @param {string} message - The user's current message
 * @param {Array<{role: string, content: string}>} history - Last N conversation turns
 * @returns {Promise<{explanation: string, code: string|null, language: string|null, is_fallback: boolean, fallback_message: string|null}>}
 */
export async function sendMessage(message, history = []) {
  const response = await fetch(`${BASE_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history }),
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
