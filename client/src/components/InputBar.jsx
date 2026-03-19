import { useRef, useState } from 'react'
import { Paperclip, Mic, ArrowUp, X } from 'lucide-react'
import { transcribeAudio } from '../api.js'

const ACCEPTED_TYPES = '.pdf,.md,.txt,.png,.jpg,.jpeg'
const MAX_FILE_BYTES = 5 * 1024 * 1024 // 5 MB

export default function InputBar({ onSend, isLoading }) {
  const textareaRef  = useRef(null)
  const fileInputRef = useRef(null)
  const mediaRecRef  = useRef(null)
  const chunksRef    = useRef([])

  const [attachedFile,   setAttachedFile]   = useState(null)
  const [isRecording,    setIsRecording]    = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const [fileError,      setFileError]      = useState(null)

  const handleInput = (e) => {
    const el = e.target
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }

  const submit = () => {
    const val = textareaRef.current?.value?.trim()
    if (!val || isLoading) return
    onSend(val, attachedFile ?? null)
    setAttachedFile(null)
    setFileError(null)
    textareaRef.current.value = ''
    textareaRef.current.style.height = 'auto'
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const handleFileChange = (e) => {
    const f = e.target.files?.[0]
    e.target.value = ''
    if (!f) return
    if (f.size > MAX_FILE_BYTES) {
      setFileError('File too large — max 5 MB')
      return
    }
    setFileError(null)
    setAttachedFile(f)
  }

  const handleMicClick = async () => {
    if (isRecording) {
      mediaRecRef.current?.stop()
      setIsRecording(false)
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream)
      chunksRef.current = []
      mr.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }
      mr.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        setIsTranscribing(true)
        try {
          const { text } = await transcribeAudio(blob)
          if (textareaRef.current && text) {
            textareaRef.current.value = text
            textareaRef.current.dispatchEvent(new Event('input', { bubbles: true }))
            textareaRef.current.focus()
          }
        } catch (err) {
          console.error('Transcription failed:', err)
        } finally {
          setIsTranscribing(false)
        }
      }
      mr.start()
      mediaRecRef.current = mr
      setIsRecording(true)
    } catch (err) {
      console.error('Microphone access denied:', err)
    }
  }

  return (
    <div className="space-y-2">

      {/* Transcribing indicator */}
      {isTranscribing && (
        <div className="flex items-center gap-2 text-xs text-gray-400 px-1">
          <span className="inline-block w-3 h-3 border-2 border-gray-300 border-t-primary rounded-full animate-spin" />
          Transcribing…
        </div>
      )}

      {/* File chip */}
      {attachedFile && (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-purple-50 border border-purple-100 rounded-xl w-fit max-w-full">
          <Paperclip size={12} className="text-purple-400 flex-shrink-0" />
          <span className="text-xs text-purple-700 truncate max-w-[220px]">{attachedFile.name}</span>
          <button
            onClick={() => { setAttachedFile(null); setFileError(null) }}
            className="text-purple-300 hover:text-purple-600 transition-colors flex-shrink-0"
            aria-label="Remove attachment"
          >
            <X size={12} />
          </button>
        </div>
      )}

      {/* File error */}
      {fileError && (
        <p className="text-xs text-red-500 px-1">{fileError}</p>
      )}

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPTED_TYPES}
        className="hidden"
        onChange={handleFileChange}
      />

      {/* Input row */}
      <div className="flex items-end gap-2 bg-gray-50 border border-gray-200 rounded-2xl px-3 py-2.5 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/10 transition-all">

        {/* Left buttons */}
        <div className="flex items-end gap-0.5 flex-shrink-0 pb-0.5">
          {/* Paperclip */}
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isLoading}
            aria-label="Attach file"
            className={`w-7 h-7 rounded-lg flex items-center justify-center transition-colors
              ${attachedFile
                ? 'text-purple-500 bg-purple-50 hover:bg-purple-100'
                : 'text-gray-400 hover:text-gray-600 hover:bg-gray-200'}
              disabled:opacity-40`}
          >
            <Paperclip size={15} />
          </button>

          {/* Mic */}
          <button
            onClick={handleMicClick}
            disabled={isLoading || isTranscribing}
            aria-label={isRecording ? 'Stop recording' : 'Start voice input'}
            className={`w-7 h-7 rounded-lg flex items-center justify-center transition-colors relative
              ${isRecording
                ? 'text-white bg-red-500 hover:bg-red-600'
                : 'text-gray-400 hover:text-gray-600 hover:bg-gray-200'}
              disabled:opacity-40`}
          >
            <Mic size={15} />
            {isRecording && (
              <span className="absolute inset-0 rounded-lg bg-red-500 animate-ping opacity-40 pointer-events-none" />
            )}
          </button>
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
    </div>
  )
}
