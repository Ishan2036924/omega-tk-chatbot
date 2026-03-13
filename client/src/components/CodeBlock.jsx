/**
 * Syntax-highlighted code block with a header bar and one-click copy.
 * Relies on highlight.js loaded globally via CDN in index.html.
 * The copy button shows "✓ Copied!" for 2 s after clicking.
 */
import { useEffect, useRef, useState } from 'react'

/** @param {{ code: string, language: string }} props */
export default function CodeBlock({ code, language }) {
  const codeRef = useRef(null)
  const [copied, setCopied] = useState(false)

  // Re-highlight whenever the code prop changes
  useEffect(() => {
    const el = codeRef.current
    if (!el || !window.hljs) return
    // Reset the "already highlighted" flag so hljs re-processes the element
    el.removeAttribute('data-highlighted')
    window.hljs.highlightElement(el)
  }, [code])

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code)
    } catch {
      // Fallback for browsers without Clipboard API
      const ta = document.createElement('textarea')
      ta.value = code
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="rounded-xl overflow-hidden border border-[#333] text-sm">
      {/* ── Header bar ── */}
      <div className="flex items-center justify-between bg-[#1a1a1a] px-4 py-2 border-b border-[#333]">
        <span className="text-xs text-gray-400 font-mono select-none">{language}</span>
        <button
          onClick={handleCopy}
          className="text-xs text-gray-400 hover:text-white transition-colors px-2 py-1 rounded hover:bg-[#333] select-none"
        >
          {copied ? '✓ Copied!' : 'Copy'}
        </button>
      </div>

      {/* ── Code area ── */}
      <div className="bg-[#0d0d0d] overflow-x-auto">
        <pre className="p-4 m-0 leading-relaxed">
          <code ref={codeRef} className={`language-${language} !bg-transparent`}>
            {code}
          </code>
        </pre>
      </div>
    </div>
  )
}
