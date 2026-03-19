import { MessageSquare, Clock, Bookmark, BarChart2, Plus, X, Zap } from 'lucide-react'

const NAV_ITEMS = [
  { icon: MessageSquare, label: 'All Chats', id: 'all' },
  { icon: Clock,         label: 'Recent',    id: 'recent' },
  { icon: Bookmark,      label: 'Saved',     id: 'saved' },
  { icon: BarChart2,     label: 'Analytics', id: 'analytics' },
]

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now - d
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24) return `${diffH}h ago`
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export default function LeftPanel({ sessions, currentSessionId, onSelectSession, onNewChat }) {
  return (
    <div className="w-[260px] h-full bg-sidebar flex flex-col select-none">

      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-white/5">
        <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center flex-shrink-0">
          <Zap size={16} className="text-white" />
        </div>
        <div>
          <p className="text-white font-semibold text-sm leading-tight">Omega TK</p>
          <p className="text-white/40 text-[10px] leading-tight">Code Assistant</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="px-3 pt-4 pb-2 space-y-0.5">
        {NAV_ITEMS.map(({ icon: Icon, label, id }) => (
          <button
            key={id}
            className={`
              w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
              ${id === 'all'
                ? 'bg-white/10 text-white'
                : 'text-white/50 hover:text-white/80 hover:bg-white/5'}
            `}
          >
            <Icon size={16} />
            <span>{label}</span>
            {id === 'analytics' && (
              <span className="ml-auto text-[9px] font-semibold bg-primary/20 text-primary px-1.5 py-0.5 rounded-full">
                SOON
              </span>
            )}
          </button>
        ))}
      </nav>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto sidebar-scroll px-3 py-2">
        {sessions.length === 0 ? (
          <div className="px-3 py-8 text-center">
            <MessageSquare size={24} className="text-white/20 mx-auto mb-2" />
            <p className="text-white/30 text-xs">No chats yet</p>
          </div>
        ) : (
          <div className="space-y-0.5">
            <p className="text-white/30 text-[10px] font-semibold uppercase tracking-widest px-3 py-2">
              Conversations
            </p>
            {sessions.map(session => (
              <button
                key={session.id}
                onClick={() => onSelectSession(session.id)}
                className={`
                  w-full text-left px-3 py-2.5 rounded-lg transition-colors group
                  ${session.id === currentSessionId
                    ? 'bg-primary/20 border border-primary/30'
                    : 'hover:bg-white/5 border border-transparent'}
                `}
              >
                <div className="flex items-start justify-between gap-2">
                  <p className={`text-xs font-medium leading-snug line-clamp-2 flex-1 ${
                    session.id === currentSessionId ? 'text-white' : 'text-white/70 group-hover:text-white/90'
                  }`}>
                    {session.title}
                  </p>
                  <span className="text-white/30 text-[10px] flex-shrink-0 pt-0.5">
                    {formatTime(session.lastActive)}
                  </span>
                </div>
                <p className="text-white/30 text-[10px] mt-1">
                  {session.messages.length} message{session.messages.length !== 1 ? 's' : ''}
                </p>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* New Chat button */}
      <div className="p-3 border-t border-white/5">
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-primary hover:bg-primary-dark transition-colors text-white text-sm font-semibold"
        >
          <Plus size={16} />
          New Chat
        </button>
      </div>
    </div>
  )
}
