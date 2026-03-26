import { useState, useRef } from 'react'
import {
  BookOpen, Upload, Plus, Trash2, FileText,
  AlertCircle, CheckCircle, X, Loader2,
} from 'lucide-react'
import { addKnowledge, addKnowledgeFile, deleteKnowledge } from '../api.js'

const ACCEPTED      = '.pdf,.md,.txt,.png,.jpg,.jpeg'
const MAX_CHARS     = 20_000  // soft cap shown in counter
const MAX_FILE_MB   = 5

// ── Sub-components ────────────────────────────────────────────────────────────

/**
 * Colour-coded relevance dot beside each source name.
 *   Green  ≥ 0.8  — high relevance
 *   Amber  ≥ 0.5  — moderate relevance
 *   Gray   null   — legacy chunk (no score stored)
 */
function ConfidenceDot({ score }) {
  if (score == null) return null
  const pct = Math.round(score * 100)
  let color, label
  if (score >= 0.8) {
    color = 'bg-emerald-400'
    label = `High relevance · ${pct}%`
  } else {
    color = 'bg-amber-400'
    label = `Moderate relevance · ${pct}%`
  }
  return (
    <span
      title={label}
      className={`inline-flex items-center gap-1 text-[10px] font-medium flex-shrink-0 ${
        score >= 0.8 ? 'text-emerald-500' : 'text-amber-500'
      }`}
    >
      <span className={`inline-block w-1.5 h-1.5 rounded-full ${color}`} />
      {pct}%
    </span>
  )
}

/** Inline result banner — replaces floating toasts inside the panel. */
function ResultBanner({ result, onDismiss }) {
  if (!result) return null
  const isSuccess = result.type === 'success'
  return (
    <div className={`flex items-start gap-2 rounded-xl px-3.5 py-3 text-xs border ${
      isSuccess
        ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
        : 'bg-red-50 border-red-200 text-red-600'
    }`}>
      <span className="flex-shrink-0 mt-0.5">
        {isSuccess
          ? <CheckCircle size={13} />
          : <AlertCircle size={13} />}
      </span>
      <span className="flex-1 leading-relaxed">{result.msg}</span>
      <button
        onClick={onDismiss}
        className="flex-shrink-0 opacity-50 hover:opacity-100 transition-opacity mt-0.5"
        aria-label="Dismiss"
      >
        <X size={12} />
      </button>
    </div>
  )
}

/** Single source row in the uploaded-sources list. */
function SourceItem({ item, onDelete, isDeleting }) {
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-3 border-t border-gray-50 group hover:bg-gray-50 transition-colors">
      <div className="flex items-center gap-2 min-w-0">
        <FileText size={13} className="text-purple-400 flex-shrink-0" />
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-xs font-medium text-gray-700 truncate">{item.source}</p>
            <ConfidenceDot score={item.avg_judge_score} />
          </div>
          <p className="text-[10px] text-gray-400 mt-0.5">
            {item.chunk_count} chunk{item.chunk_count !== 1 ? 's' : ''}
            {item.created_at
              ? ` · ${new Date(item.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`
              : ''}
          </p>
        </div>
      </div>
      <button
        onClick={() => onDelete(item.id)}
        disabled={isDeleting === item.id}
        className="p-1.5 rounded-lg text-gray-300 hover:text-red-400 hover:bg-red-50 transition-colors disabled:opacity-40 flex-shrink-0"
        aria-label={`Delete ${item.source}`}
      >
        {isDeleting === item.id
          ? <Loader2 size={13} className="animate-spin" />
          : <Trash2 size={13} />}
      </button>
    </div>
  )
}

/** Loading skeleton row — shown while fetching sources on mount. */
function SkeletonRow() {
  return (
    <div className="flex items-center gap-3 px-4 py-3 border-t border-gray-50 animate-pulse">
      <div className="w-3 h-3 rounded bg-gray-100 flex-shrink-0" />
      <div className="flex-1 space-y-1.5">
        <div className="h-2.5 bg-gray-100 rounded w-3/5" />
        <div className="h-2 bg-gray-100 rounded w-2/5" />
      </div>
      <div className="w-6 h-6 rounded-lg bg-gray-100 flex-shrink-0" />
    </div>
  )
}

// ── Main panel ────────────────────────────────────────────────────────────────

/**
 * KnowledgePanel
 *
 * Props:
 *   sessionId         — current chat session ID (used when adding new chunks)
 *   token             — Supabase JWT access token
 *   sources           — array of source objects from App.jsx global state
 *   isLoadingSources  — true while App.jsx is fetching sources on init
 *   onRefreshSources  — callback: tells App.jsx to re-fetch from /api/knowledge/me
 *
 * Sources are owned by the USER (not the session). They are fetched once during
 * app initialisation and passed down here — KnowledgePanel never self-fetches.
 * After any add/delete operation it calls onRefreshSources() to keep App state
 * in sync, which automatically propagates back here via props.
 */
export default function KnowledgePanel({
  sessionId,
  token = null,
  sources = [],
  isLoadingSources = false,
  onRefreshSources,
}) {
  // Text-paste state
  const [pasteText, setPasteText]   = useState('')
  const [sourceName, setSourceName] = useState('')
  const [textResult, setTextResult] = useState(null)   // {type, msg}
  const [isAddingText, setIsAddingText] = useState(false)

  // File-upload state
  const [pendingFile, setPendingFile]   = useState(null)   // File object staged for upload
  const [fileResult, setFileResult]     = useState(null)   // {type, msg}
  const [isAddingFile, setIsAddingFile] = useState(false)
  const [isDragging, setIsDragging]     = useState(false)
  const fileInputRef                    = useRef(null)

  // Per-row delete spinner
  const [isDeleting, setIsDeleting] = useState(null)

  // ── Add pasted text ───────────────────────────────────────────────────────
  const handleAddText = async () => {
    if (!pasteText.trim()) return
    if (!sessionId) {
      setTextResult({ type: 'error', msg: 'No active session — send a message first.' })
      return
    }
    const name = sourceName.trim() || `note-${Date.now()}`
    setTextResult(null)
    setIsAddingText(true)
    try {
      const res = await addKnowledge(pasteText, name, sessionId, token)
      if (res.accepted === false) {
        setTextResult({ type: 'error', msg: `Rejected — not Omega TK related: ${res.reason}` })
      } else {
        const pct = res.confidence != null ? ` (confidence: ${Math.round(res.confidence * 100)}%)` : ''
        setTextResult({
          type: 'success',
          msg: `Added ${res.chunks_added} chunk${res.chunks_added !== 1 ? 's' : ''} from "${name}"${pct}`,
        })
        setPasteText('')
        setSourceName('')
        onRefreshSources?.()
      }
    } catch (err) {
      setTextResult({ type: 'error', msg: err.message })
    } finally {
      setIsAddingText(false)
    }
  }

  // ── Stage a file (show chip) ──────────────────────────────────────────────
  const handleFilePick = (file) => {
    if (!file) return
    if (file.size > MAX_FILE_MB * 1024 * 1024) {
      setFileResult({ type: 'error', msg: `File too large — max ${MAX_FILE_MB} MB` })
      return
    }
    setFileResult(null)
    setPendingFile(file)
  }

  // ── Upload staged file ─────────────────────────────────────────────────────
  const handleUploadFile = async () => {
    if (!pendingFile) return
    if (!sessionId) {
      setFileResult({ type: 'error', msg: 'No active session — send a message first.' })
      return
    }
    setIsAddingFile(true)
    try {
      const res = await addKnowledgeFile(pendingFile, sessionId, token)
      if (res.accepted === false) {
        setFileResult({ type: 'error', msg: `Rejected — not Omega TK related: ${res.reason}` })
      } else {
        const pct = res.confidence != null ? ` (confidence: ${Math.round(res.confidence * 100)}%)` : ''
        setFileResult({
          type: 'success',
          msg: `Added ${res.chunks_added} chunk${res.chunks_added !== 1 ? 's' : ''} from "${res.source}"${pct}`,
        })
        setPendingFile(null)
        onRefreshSources?.()
      }
    } catch (err) {
      setFileResult({ type: 'error', msg: err.message })
    } finally {
      setIsAddingFile(false)
    }
  }

  const handleDelete = async (chunkId) => {
    setIsDeleting(chunkId)
    try {
      await deleteKnowledge(chunkId, token)
      // Delegate the update to App-level state — onRefreshSources re-fetches
      // from the server so the list reflects the actual DB state.
      onRefreshSources?.()
    } catch (err) {
      setFileResult({ type: 'error', msg: `Delete failed: ${err.message}` })
    } finally {
      setIsDeleting(null)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleFilePick(file)
  }

  const charCount   = pasteText.length
  const charWarning = charCount > MAX_CHARS

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="h-full overflow-y-auto custom-scroll bg-gray-50">

      {/* Sticky header */}
      <div className="sticky top-0 bg-gray-50 border-b border-gray-100 px-6 py-4 z-10">
        <div className="flex items-center gap-2">
          <BookOpen size={15} className="text-purple-500" />
          <h2 className="text-sm font-semibold text-gray-800">Knowledge Base</h2>
        </div>
        <p className="text-[11px] text-gray-400 mt-0.5 ml-[23px]">
          Enrich the assistant with your own docs · persists across all your sessions
        </p>
      </div>

      <div className="p-6 space-y-5">

        {/* ── Input row: two cards side-by-side ─────────────────────────── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">

          {/* Paste Text card */}
          <div className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm space-y-3 flex flex-col">
            <h3 className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
              Paste Text
            </h3>

            <input
              type="text"
              value={sourceName}
              onChange={e => setSourceName(e.target.value)}
              placeholder="Source name (e.g. my-protocol)"
              className="w-full text-xs text-gray-700 placeholder-gray-300 border border-gray-100 rounded-lg px-3 py-2 outline-none focus:border-primary focus:ring-1 focus:ring-primary/20 transition-all"
            />

            <div className="relative flex-1">
              <textarea
                value={pasteText}
                onChange={e => setPasteText(e.target.value)}
                placeholder="Paste documentation, notes, or any text content here…"
                rows={7}
                className={`w-full text-xs text-gray-700 placeholder-gray-300 border rounded-lg px-3 py-2 outline-none focus:ring-1 transition-all resize-none leading-relaxed ${
                  charWarning
                    ? 'border-amber-300 focus:border-amber-400 focus:ring-amber-100'
                    : 'border-gray-100 focus:border-primary focus:ring-primary/20'
                }`}
              />
              {/* Character counter */}
              <span className={`absolute bottom-2 right-3 text-[10px] pointer-events-none ${
                charWarning ? 'text-amber-400' : 'text-gray-300'
              }`}>
                {charCount.toLocaleString()}{charWarning ? ` / ${MAX_CHARS.toLocaleString()}` : ''}
              </span>
            </div>

            {/* Inline result banner */}
            <ResultBanner result={textResult} onDismiss={() => setTextResult(null)} />

            <button
              onClick={handleAddText}
              disabled={!pasteText.trim() || isAddingText}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary hover:bg-primary-dark text-white text-xs font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed mt-auto"
            >
              {isAddingText
                ? <><Loader2 size={12} className="animate-spin" /> Processing…</>
                : <><Plus size={12} /> Add to Knowledge Base</>}
            </button>
          </div>

          {/* Upload File card */}
          <div className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm space-y-3 flex flex-col">
            <h3 className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
              Upload File
            </h3>

            {/* Drop zone */}
            <div
              onDragOver={e => { e.preventDefault(); setIsDragging(true) }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              onClick={() => !pendingFile && fileInputRef.current?.click()}
              className={`
                border-2 border-dashed rounded-xl p-6 text-center transition-colors flex-1
                ${pendingFile
                  ? 'border-gray-200 bg-gray-50 cursor-default'
                  : isDragging
                    ? 'border-primary bg-primary/5 cursor-pointer'
                    : 'border-gray-200 hover:border-primary/40 hover:bg-gray-50 cursor-pointer'}
              `}
            >
              {pendingFile ? (
                /* File chip */
                <div className="flex flex-col items-center gap-3">
                  <div className="flex items-center gap-2 bg-purple-50 border border-purple-100 rounded-lg px-3 py-2 max-w-full">
                    <FileText size={13} className="text-purple-400 flex-shrink-0" />
                    <span className="text-xs text-purple-700 font-medium truncate max-w-[140px]">
                      {pendingFile.name}
                    </span>
                    <span className="text-[10px] text-purple-400 flex-shrink-0">
                      {(pendingFile.size / 1024).toFixed(0)} KB
                    </span>
                    <button
                      onClick={e => { e.stopPropagation(); setPendingFile(null) }}
                      className="text-purple-300 hover:text-purple-500 transition-colors flex-shrink-0"
                      aria-label="Remove file"
                    >
                      <X size={12} />
                    </button>
                  </div>
                  <p className="text-[10px] text-gray-400">
                    Click "Upload &amp; Analyze" below to process this file
                  </p>
                </div>
              ) : (
                <>
                  <Upload size={20} className={`mx-auto mb-2 ${isDragging ? 'text-primary' : 'text-gray-300'}`} />
                  <p className="text-xs text-gray-400">Drag & drop or click to select</p>
                  <p className="text-[10px] text-gray-300 mt-1">PDF, TXT, MD, PNG, JPG · max {MAX_FILE_MB} MB</p>
                </>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept={ACCEPTED}
                className="hidden"
                onChange={e => { handleFilePick(e.target.files?.[0]); e.target.value = '' }}
              />
            </div>

            {/* Inline result banner */}
            <ResultBanner result={fileResult} onDismiss={() => setFileResult(null)} />

            {/* Upload & Analyze — only active when a file is staged */}
            <button
              onClick={handleUploadFile}
              disabled={!pendingFile || isAddingFile}
              className="flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg bg-primary hover:bg-primary-dark text-white text-xs font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed mt-auto"
            >
              {isAddingFile
                ? <><Loader2 size={12} className="animate-spin" /> Analyzing…</>
                : <><Upload size={12} /> Upload &amp; Analyze</>}
            </button>
          </div>
        </div>

        {/* ── Uploaded sources list ──────────────────────────────────────── */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-50 flex items-center justify-between">
            <h3 className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
              Uploaded Sources
            </h3>
            {!isLoadingSources && sources.length > 0 && (
              <span className="text-[10px] text-gray-300">
                {sources.length} source{sources.length !== 1 ? 's' : ''}
              </span>
            )}
          </div>

          {isLoadingSources ? (
            /* Loading skeleton */
            <>
              <SkeletonRow />
              <SkeletonRow />
              <SkeletonRow />
            </>
          ) : sources.length === 0 ? (
            <div className="p-8 text-center">
              <BookOpen size={20} className="text-gray-200 mx-auto mb-2" />
              <p className="text-gray-300 text-xs">No sources added yet</p>
              <p className="text-gray-200 text-[10px] mt-1">Add text or upload a file above</p>
            </div>
          ) : (
            sources.map(item => (
              <SourceItem
                key={item.id}
                item={item}
                onDelete={handleDelete}
                isDeleting={isDeleting}
              />
            ))
          )}
        </div>

        {/* Info footnote */}
        {sources.length > 0 && !isLoadingSources && (
          <p className="text-[10px] text-gray-300 leading-relaxed px-1">
            Knowledge chunks are retrieved alongside FAISS docs in every session for your account.
          </p>
        )}

      </div>
    </div>
  )
}
