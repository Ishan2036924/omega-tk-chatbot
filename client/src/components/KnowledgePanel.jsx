import { useState, useEffect, useRef, useCallback } from 'react'
import { BookOpen, Upload, Plus, Trash2, FileText, AlertCircle, CheckCircle } from 'lucide-react'
import { addKnowledge, addKnowledgeFile, listKnowledge, deleteKnowledge } from '../api.js'

const ACCEPTED = '.pdf,.md,.txt,.png,.jpg,.jpeg'

/**
 * Confidence dot — colour-codes the judge score for each knowledge source.
 *   Green  ≥ 0.8   — high relevance
 *   Yellow 0.5–0.8 — moderate relevance
 *   Gray   null    — legacy chunk (pre-Feature-2, no score recorded)
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
      className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${color}`}
    />
  )
}

function SourceItem({ item, onDelete, isDeleting }) {
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-3 border-t border-gray-50 group hover:bg-gray-50 transition-colors">
      <div className="flex items-center gap-2 min-w-0">
        <FileText size={13} className="text-purple-400 flex-shrink-0" />
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <p className="text-xs font-medium text-gray-700 truncate">{item.source}</p>
            <ConfidenceDot score={item.avg_judge_score} />
          </div>
          <p className="text-[10px] text-gray-400 mt-0.5">
            {item.chunk_count} chunk{item.chunk_count !== 1 ? 's' : ''}
            {item.created_at ? ` · ${new Date(item.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}` : ''}
          </p>
        </div>
      </div>
      <button
        onClick={() => onDelete(item.id, item.source)}
        disabled={isDeleting === item.id}
        className="p-1.5 rounded-lg text-gray-300 hover:text-red-400 hover:bg-red-50 transition-colors disabled:opacity-40 flex-shrink-0"
        aria-label={`Delete ${item.source}`}
      >
        <Trash2 size={13} />
      </button>
    </div>
  )
}

export default function KnowledgePanel({ sessionId, token = null }) {
  const [sources, setSources]         = useState([])
  const [pasteText, setPasteText]     = useState('')
  const [sourceName, setSourceName]   = useState('')
  const [isAdding, setIsAdding]       = useState(false)
  const [isDeleting, setIsDeleting]   = useState(null)
  const [isDragging, setIsDragging]   = useState(false)
  const [toast, setToast]             = useState(null) // {type: 'success'|'error', msg}
  const fileInputRef                  = useRef(null)

  const showToast = (type, msg) => {
    setToast({ type, msg })
    setTimeout(() => setToast(null), 4000)
  }

  const loadSources = useCallback(async () => {
    if (!sessionId) return
    const data = await listKnowledge(sessionId, token)
    setSources(data || [])
  }, [sessionId, token])

  useEffect(() => { loadSources() }, [loadSources])

  const handleAddText = async () => {
    if (!pasteText.trim()) return
    if (!sessionId) { showToast('error', 'No active session — send a message first'); return }
    const name = sourceName.trim() || `note-${Date.now()}`
    setIsAdding(true)
    try {
      const res = await addKnowledge(pasteText, name, sessionId, token)
      if (res.accepted === false) {
        // LLM judge rejected the content
        showToast('error', `Rejected — not Omega TK related: ${res.reason}`)
      } else {
        const pct = res.confidence != null ? ` (confidence: ${Math.round(res.confidence * 100)}%)` : ''
        showToast('success', `Added ${res.chunks_added} chunk${res.chunks_added !== 1 ? 's' : ''} from "${name}" ✓${pct}`)
        setPasteText('')
        setSourceName('')
        await loadSources()
      }
    } catch (err) {
      showToast('error', err.message)
    } finally {
      setIsAdding(false)
    }
  }

  const handleFileUpload = async (file) => {
    if (!file) return
    if (!sessionId) { showToast('error', 'No active session — send a message first'); return }
    if (file.size > 5 * 1024 * 1024) { showToast('error', 'File too large — max 5 MB'); return }
    setIsAdding(true)
    try {
      const res = await addKnowledgeFile(file, sessionId, token)
      if (res.accepted === false) {
        // LLM judge rejected the file content
        showToast('error', `Rejected — not Omega TK related: ${res.reason}`)
      } else {
        const pct = res.confidence != null ? ` (confidence: ${Math.round(res.confidence * 100)}%)` : ''
        showToast('success', `Added ${res.chunks_added} chunk${res.chunks_added !== 1 ? 's' : ''} from "${res.source}" ✓${pct}`)
        await loadSources()
      }
    } catch (err) {
      showToast('error', err.message)
    } finally {
      setIsAdding(false)
    }
  }

  const handleDelete = async (chunkId, source) => {
    setIsDeleting(chunkId)
    try {
      await deleteKnowledge(chunkId, token)
      showToast('success', `Deleted "${source}"`)
      setSources(prev => prev.filter(s => s.id !== chunkId))
    } catch (err) {
      showToast('error', err.message)
    } finally {
      setIsDeleting(null)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleFileUpload(file)
  }

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

        {/* Toast */}
        {toast && (
          <div className={`flex items-start gap-2 rounded-xl px-4 py-3 text-xs border ${
            toast.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
              : 'bg-red-50 border-red-200 text-red-600'
          }`}>
            {toast.type === 'success'
              ? <CheckCircle size={13} className="flex-shrink-0 mt-0.5" />
              : <AlertCircle size={13} className="flex-shrink-0 mt-0.5" />}
            {toast.msg}
          </div>
        )}

        {/* Paste text input */}
        <div className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm space-y-3">
          <h3 className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Paste Text</h3>

          <input
            type="text"
            value={sourceName}
            onChange={e => setSourceName(e.target.value)}
            placeholder="Source name (e.g. my-protocol, meeting-notes)"
            className="w-full text-xs text-gray-700 placeholder-gray-300 border border-gray-100 rounded-lg px-3 py-2 outline-none focus:border-primary focus:ring-1 focus:ring-primary/20 transition-all"
          />

          <textarea
            value={pasteText}
            onChange={e => setPasteText(e.target.value)}
            placeholder="Paste documentation, notes, or any text content here…"
            rows={6}
            className="w-full text-xs text-gray-700 placeholder-gray-300 border border-gray-100 rounded-lg px-3 py-2 outline-none focus:border-primary focus:ring-1 focus:ring-primary/20 transition-all resize-none leading-relaxed"
          />

          <button
            onClick={handleAddText}
            disabled={!pasteText.trim() || isAdding}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary hover:bg-primary-dark text-white text-xs font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {isAdding ? (
              <span className="inline-block w-3 h-3 border-2 border-white/40 border-t-white rounded-full animate-spin" />
            ) : (
              <Plus size={13} />
            )}
            {isAdding ? 'Processing…' : 'Add to Knowledge Base'}
          </button>
        </div>

        {/* File upload drop zone */}
        <div className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm space-y-3">
          <h3 className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Upload File</h3>

          <div
            onDragOver={e => { e.preventDefault(); setIsDragging(true) }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`
              border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors
              ${isDragging
                ? 'border-primary bg-primary/5'
                : 'border-gray-200 hover:border-primary/40 hover:bg-gray-50'}
            `}
          >
            <Upload size={20} className={`mx-auto mb-2 ${isDragging ? 'text-primary' : 'text-gray-300'}`} />
            <p className="text-xs text-gray-400">
              {isAdding ? 'Processing…' : 'Drag & drop or click to upload'}
            </p>
            <p className="text-[10px] text-gray-300 mt-1">PDF, TXT, MD, PNG, JPG · max 5 MB</p>
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED}
              className="hidden"
              onChange={e => { handleFileUpload(e.target.files?.[0]); e.target.value = '' }}
            />
          </div>
        </div>

        {/* Uploaded sources list */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-50 flex items-center justify-between">
            <h3 className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
              Uploaded Sources
            </h3>
            {sources.length > 0 && (
              <span className="text-[10px] text-gray-300">{sources.length} source{sources.length !== 1 ? 's' : ''}</span>
            )}
          </div>

          {sources.length === 0 ? (
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

        {/* Info note */}
        {sources.length > 0 && (
          <div className="text-[10px] text-gray-300 leading-relaxed px-1">
            Knowledge chunks are retrieved alongside FAISS docs in every session for your account.
          </div>
        )}

      </div>
    </div>
  )
}
