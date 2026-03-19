import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, TrendingUp, Code2, ShieldAlert, Clock } from 'lucide-react'
import { fetchAnalytics } from '../api.js'

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-4 flex items-start gap-3 shadow-sm">
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${color}`}>
        <Icon size={16} className="text-white" />
      </div>
      <div className="min-w-0">
        <p className="text-2xl font-bold text-gray-800 leading-tight">{value}</p>
        <p className="text-xs text-gray-400 mt-0.5 leading-tight">{label}</p>
      </div>
    </div>
  )
}

function BarChart({ data }) {
  if (!data?.length) return null
  const max = Math.max(...data.map(d => d.count), 1)
  const BAR_W = 18
  const BAR_GAP = 3
  const HEIGHT = 72
  const totalW = data.length * (BAR_W + BAR_GAP)

  return (
    <div className="overflow-x-auto">
      <svg width={totalW} height={HEIGHT + 18} aria-label="Queries per hour bar chart">
        {data.map((d, i) => {
          const barH = Math.max(2, (d.count / max) * HEIGHT)
          const x = i * (BAR_W + BAR_GAP)
          const y = HEIGHT - barH
          return (
            <g key={`${d.hour}-${i}`}>
              <rect
                x={x} y={y} width={BAR_W} height={barH} rx={3}
                fill={d.count > 0 ? '#7c3aed' : '#f3f4f6'}
              />
              {i % 6 === 0 && (
                <text
                  x={x + BAR_W / 2} y={HEIGHT + 14}
                  textAnchor="middle" fontSize={8} fill="#9ca3af"
                >
                  {d.hour}
                </text>
              )}
            </g>
          )
        })}
      </svg>
    </div>
  )
}

function IntentBadge({ intent }) {
  const styles = {
    CODE:         'bg-purple-50 text-purple-600',
    CONVERSATION: 'bg-blue-50 text-blue-600',
    OFF_TOPIC:    'bg-red-50 text-red-500',
    GREETING:     'bg-green-50 text-green-600',
  }
  return (
    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${styles[intent] ?? 'bg-gray-100 text-gray-500'}`}>
      {intent ?? '—'}
    </span>
  )
}

export default function AnalyticsDashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetchAnalytics()
      if (result.error) setError(result.error)
      setData(result)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <div className="h-full overflow-y-auto custom-scroll bg-gray-50">

      {/* Sticky header */}
      <div className="sticky top-0 bg-gray-50 border-b border-gray-100 px-6 py-4 flex items-center justify-between z-10">
        <div>
          <h2 className="text-sm font-semibold text-gray-800">Analytics</h2>
          <p className="text-[11px] text-gray-400 mt-0.5">Last 24 hours · from Supabase queries_log</p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-gray-500 hover:text-gray-800 hover:bg-white border border-gray-200 transition-colors disabled:opacity-40"
        >
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      <div className="p-6 space-y-5">

        {/* Config error */}
        {error && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-xs text-amber-700 leading-relaxed">
            {error.toLowerCase().includes('supabase') || error.toLowerCase().includes('not configured')
              ? '⚠ Supabase is not configured. Add SUPABASE_URL and SUPABASE_KEY to your Render environment variables to enable analytics.'
              : `Error: ${error}`}
          </div>
        )}

        {/* Stat cards */}
        <div className="grid grid-cols-2 gap-3">
          <StatCard
            icon={TrendingUp} label="Total Queries (24h)"
            value={loading ? '…' : (data?.total_queries ?? 0)}
            color="bg-blue-500"
          />
          <StatCard
            icon={Code2} label="Code Requests"
            value={loading ? '…' : (data?.code_requests ?? 0)}
            color="bg-primary"
          />
          <StatCard
            icon={ShieldAlert} label="Guardrail Blocks"
            value={loading ? '…' : (data?.guardrail_blocks ?? 0)}
            color="bg-orange-500"
          />
          <StatCard
            icon={Clock} label="Avg Latency (ms)"
            value={loading ? '…' : (data?.avg_latency ?? 0)}
            color="bg-green-500"
          />
        </div>

        {/* Bar chart */}
        <div className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm">
          <h3 className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-3">
            Queries per Hour (last 24 h)
          </h3>
          {loading ? (
            <div className="h-20 flex items-center justify-center text-gray-300 text-sm">Loading…</div>
          ) : data?.hourly_counts?.length ? (
            <BarChart data={data.hourly_counts} />
          ) : (
            <div className="h-20 flex items-center justify-center text-gray-300 text-sm">No data yet</div>
          )}
        </div>

        {/* Recent queries table */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-50 flex items-center justify-between">
            <h3 className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
              Recent Queries
            </h3>
            {data?.recent_queries?.length > 0 && (
              <span className="text-[10px] text-gray-300">{data.recent_queries.length} shown</span>
            )}
          </div>

          {loading ? (
            <div className="p-8 text-center text-gray-300 text-sm">Loading…</div>
          ) : !data?.recent_queries?.length ? (
            <div className="p-8 text-center text-gray-300 text-sm">No queries logged yet</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-gray-50 text-gray-400 text-left">
                    <th className="px-4 py-2.5 font-medium whitespace-nowrap">Time</th>
                    <th className="px-4 py-2.5 font-medium">Message</th>
                    <th className="px-4 py-2.5 font-medium">Intent</th>
                    <th className="px-4 py-2.5 font-medium">Status</th>
                    <th className="px-4 py-2.5 font-medium text-right whitespace-nowrap">Latency</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_queries.map((q, i) => (
                    <tr key={i} className="border-t border-gray-50 hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-2.5 text-gray-400 whitespace-nowrap">
                        {q.timestamp
                          ? new Date(q.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
                          : '—'}
                      </td>
                      <td className="px-4 py-2.5 text-gray-600 max-w-[180px] truncate" title={q.message}>
                        {q.message || '—'}
                      </td>
                      <td className="px-4 py-2.5">
                        <IntentBadge intent={q.intent} />
                      </td>
                      <td className="px-4 py-2.5">
                        {q.is_fallback
                          ? <span className="text-orange-500 font-medium">Blocked</span>
                          : q.has_code
                            ? <span className="text-purple-600 font-medium">Code</span>
                            : <span className="text-blue-500 font-medium">Answer</span>}
                      </td>
                      <td className="px-4 py-2.5 text-gray-400 text-right">
                        {q.latency_ms ? `${q.latency_ms} ms` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

      </div>
    </div>
  )
}
