import { useRef, useState } from 'react'
import { Paperclip, Mic, ArrowUp } from 'lucide-react'

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
    <div className="flex items-end gap-2 bg-gray-50 border border-gray-200 rounded-2xl px-3 py-2.5 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/10 transition-all">

      {/* Left: placeholder action buttons */}
      <div className="flex items-end gap-0.5 flex-shrink-0 pb-0.5">
        <div className="relative">
          <button
            onClick={() => showTooltip('attach')}
            aria-label="Attach file (coming soon)"
            className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-400 hover:text-gray-600 hover:bg-gray-200 transition-colors"
          >
            <Paperclip size={15} />
          </button>
          {tooltip === 'attach' && (
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-gray-800 text-white text-[10px] rounded-md whitespace-nowrap pointer-events-none shadow-lg z-10">
              Coming soon
            </div>
          )}
        </div>
        <div className="relative">
          <button
            onClick={() => showTooltip('mic')}
            aria-label="Voice input (coming soon)"
            className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-400 hover:text-gray-600 hover:bg-gray-200 transition-colors"
          >
            <Mic size={15} />
          </button>
          {tooltip === 'mic' && (
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-gray-800 text-white text-[10px] rounded-md whitespace-nowrap pointer-events-none shadow-lg z-10">
              Coming soon
            </div>
          )}
        </div>
      </div>

      {/* Textarea */}
      <textarea
        ref={textareaRef}
        rows={1}
        placeholder="Ask about Omega TK…"
        disabled={isLoading}
        onInput={handleInput}
        onKeyDown={handleKeyDown}
        className="flex-1 bg-transparent text-sm text-gray-800 placeholder-gray-400 resize-none outline-none max-h-48 overflow-y-auto leading-relaxed disabled:opacity-50 py-0.5"
      />

      {/* Send button */}
      <button
        onClick={submit}
        disabled={isLoading}
        aria-label="Send message"
        className="w-8 h-8 rounded-xl bg-primary hover:bg-primary-dark text-white flex items-center justify-center flex-shrink-0 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        <ArrowUp size={15} strokeWidth={2.5} />
      </button>
    </div>
  )
}
