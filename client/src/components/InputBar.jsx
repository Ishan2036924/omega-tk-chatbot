/**
 * Input bar — ChatGPT-style, identical on welcome and chat screens.
 *
 * Layout: [Paperclip] [Mic] [textarea ─── flex-1] [Send]
 * Enter sends; Shift+Enter inserts a newline.
 * Textarea auto-resizes up to ~200px.
 * Attach and Mic are placeholders with "Coming soon" tooltip.
 */
import { useRef, useState } from 'react'
import { Paperclip, Mic, ArrowUp } from 'lucide-react'

/** @param {{ onSend: (text: string) => void, isLoading: boolean }} props */
export default function InputBar({ onSend, isLoading }) {
  const textareaRef = useRef(null)
  const [tooltip, setTooltip] = useState(null) // 'attach' | 'mic' | null

  const handleInput = (e) => {
    const el = e.target
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }

  const submit = () => {
    const val = textareaRef.current?.value?.trim()
    if (!val || isLoading) return
    onSend(val)
    textareaRef.current.value = ''
    textareaRef.current.style.height = 'auto'
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const showTooltip = (id) => {
    setTooltip(id)
    setTimeout(() => setTooltip(null), 1500)
  }

  return (
    <div className="flex items-end gap-2 bg-[#2f2f2f] rounded-2xl px-3 py-3 border border-[#424242] focus-within:border-[#555] transition-colors">

      {/* ── Left: placeholder action buttons ── */}
      <div className="flex items-end gap-0.5 flex-shrink-0 pb-0.5">

        {/* Attach */}
        <div className="relative">
          <button
            onClick={() => showTooltip('attach')}
            aria-label="Attach file (coming soon)"
            className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-600 hover:text-gray-400 hover:bg-[#3a3a3a] transition-colors"
          >
            <Paperclip size={15} />
          </button>
          {tooltip === 'attach' && (
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-[#444] text-xs text-gray-200 rounded-md whitespace-nowrap pointer-events-none shadow-lg z-10">
              Coming soon
            </div>
          )}
        </div>

        {/* Mic */}
        <div className="relative">
          <button
            onClick={() => showTooltip('mic')}
            aria-label="Voice input (coming soon)"
            className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-600 hover:text-gray-400 hover:bg-[#3a3a3a] transition-colors"
          >
            <Mic size={15} />
          </button>
          {tooltip === 'mic' && (
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-[#444] text-xs text-gray-200 rounded-md whitespace-nowrap pointer-events-none shadow-lg z-10">
              Coming soon
            </div>
          )}
        </div>
      </div>

      {/* ── Textarea ── */}
      <textarea
        ref={textareaRef}
        rows={1}
        placeholder="Ask about Omega TK…"
        disabled={isLoading}
        onInput={handleInput}
        onKeyDown={handleKeyDown}
        className="flex-1 bg-transparent text-sm text-white placeholder-gray-500 resize-none outline-none max-h-48 overflow-y-auto leading-relaxed disabled:opacity-50"
      />

      {/* ── Send button ── */}
      <button
        onClick={submit}
        disabled={isLoading}
        aria-label="Send message"
        className="w-8 h-8 rounded-lg bg-white hover:bg-gray-200 text-black flex items-center justify-center flex-shrink-0 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        <ArrowUp size={14} strokeWidth={2.5} />
      </button>
    </div>
  )
}
