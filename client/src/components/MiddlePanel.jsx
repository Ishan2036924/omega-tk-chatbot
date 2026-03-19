import { Share2, Menu, PanelRight } from 'lucide-react'
import MessageList from './MessageList.jsx'
import InputBar from './InputBar.jsx'
import WelcomeScreen from './WelcomeScreen.jsx'
import AnalyticsDashboard from './AnalyticsDashboard.jsx'

export default function MiddlePanel({
  session, messages, isLoading,
  onSend, onFeedback, onExport,
  onToggleLeft, onToggleRight,
  view,
}) {
  const hasMessages = messages.length > 0

  if (view === 'analytics') {
    return (
      <div className="flex flex-col h-full bg-white min-w-0">
        {/* Header */}
        <div className="shrink-0 flex items-center justify-between px-4 py-3 border-b border-gray-100 bg-white">
          <div className="flex items-center gap-3">
            <button
              onClick={onToggleLeft}
              className="lg:hidden p-1.5 rounded-lg hover:bg-gray-100 transition-colors text-gray-500"
            >
              <Menu size={18} />
            </button>
            <h1 className="text-sm font-semibold text-gray-800 leading-tight">Analytics</h1>
          </div>
        </div>
        <div className="flex-1 min-h-0">
          <AnalyticsDashboard />
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full bg-white min-w-0">

      {/* Header */}
      <div className="shrink-0 flex items-center justify-between px-4 py-3 border-b border-gray-100 bg-white">
        <div className="flex items-center gap-3">
          {/* Mobile: toggle left panel */}
          <button
            onClick={onToggleLeft}
            className="lg:hidden p-1.5 rounded-lg hover:bg-gray-100 transition-colors text-gray-500"
          >
            <Menu size={18} />
          </button>
          <div>
            <h1 className="text-sm font-semibold text-gray-800 leading-tight">
              {session ? (
                <span className="line-clamp-1 max-w-[260px] sm:max-w-xs">{session.title}</span>
              ) : (
                'Omega TK Assistant'
              )}
            </h1>
            {session && (
              <p className="text-[10px] text-gray-400 font-normal">
                Session · {session.messages.length} messages
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onExport}
            disabled={!hasMessages}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-gray-500 hover:text-gray-800 hover:bg-gray-100 transition-colors text-xs font-medium disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <Share2 size={13} />
            <span className="hidden sm:inline">Export</span>
          </button>
          {/* Mobile: toggle right panel */}
          <button
            onClick={onToggleRight}
            className="lg:hidden p-1.5 rounded-lg hover:bg-gray-100 transition-colors text-gray-500"
          >
            <PanelRight size={18} />
          </button>
        </div>
      </div>

      {/* Messages or Welcome */}
      <div className="flex-1 overflow-y-auto custom-scroll">
        {!hasMessages ? (
          <WelcomeScreen onSend={onSend} />
        ) : (
          <MessageList messages={messages} isLoading={isLoading} onFeedback={onFeedback} />
        )}
      </div>

      {/* Input bar */}
      <div className="shrink-0 border-t border-gray-100 bg-white px-4 py-3">
        <InputBar onSend={onSend} isLoading={isLoading} />
      </div>
    </div>
  )
}
