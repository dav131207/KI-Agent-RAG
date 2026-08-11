import { useEffect, useMemo, useState } from 'react'
import ArtApprovals from './ArtApprovals'

const API_BASE = import.meta.env.VITE_API_URL || ''
const TOKEN_KEY = 'admin_token'

// Sequential hue (magnitude) — see dataviz palette: blue, light -> dark.
const BAR_FILL = 'bg-[#2a78d6] dark:bg-[#3987e5]'
const TRACK = 'bg-brand-100 dark:bg-brand-700'
const GRID = 'border-brand-200/60 dark:border-white/10'

function LoginForm({ onLogin }) {
  const [token, setToken] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/admin/verify-token`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error('Invalid token')
      localStorage.setItem(TOKEN_KEY, token)
      onLogin(token)
    } catch (err) {
      setError(err.message || 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-brand-50 dark:bg-brand-900">
      <div className="w-full max-w-md">
        <div className="bg-white dark:bg-brand-800 rounded-2xl p-6 shadow-sm border border-brand-100 dark:border-white/10">
          <h1 className="text-2xl font-black mb-2 text-brand-900 dark:text-brand-50">Professor Pepe</h1>
          <p className="text-sm text-brand-600 dark:text-brand-400 mb-6">Analytics Dashboard</p>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2 text-brand-900 dark:text-brand-50">
                Admin Token
              </label>
              <input
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Enter your admin token"
                className="w-full px-4 py-2 border border-brand-200 dark:border-white/10 rounded-lg bg-white dark:bg-brand-700 text-brand-900 dark:text-brand-50 placeholder-brand-500 focus:outline-none focus:ring-2 focus:ring-accent"
                disabled={loading}
              />
            </div>
            {error && <p className="text-sm text-red-500">{error}</p>}
            <button
              type="submit"
              disabled={loading || !token}
              className="w-full px-4 py-2 bg-accent hover:bg-accent/90 disabled:bg-brand-300 dark:disabled:bg-brand-600 text-white font-semibold rounded-lg transition-colors"
            >
              {loading ? 'Verifying...' : 'Login'}
            </button>
          </form>
          <p className="text-xs text-brand-600 dark:text-brand-400 mt-4">
            Set the <code className="bg-brand-100 dark:bg-brand-700 px-1 rounded">ADMIN_TOKEN</code> environment variable to access.
          </p>
        </div>
      </div>
    </div>
  )
}

function Card({ title, subtitle, children, className = '', action }) {
  return (
    <div className={`bg-white dark:bg-brand-800 rounded-2xl p-4 shadow-sm border border-brand-100 dark:border-white/10 ${className}`}>
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-bold text-brand-900 dark:text-brand-50">{title}</h3>
          {subtitle && <p className="text-[11px] text-brand-500 dark:text-brand-400">{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </div>
  )
}

function StatTile({ label, value, accentClass = 'text-brand-900 dark:text-brand-50' }) {
  return (
    <div className="bg-white dark:bg-brand-800 rounded-2xl p-4 shadow-sm border border-brand-100 dark:border-white/10">
      <p className="text-xs font-medium text-brand-500 dark:text-brand-400 mb-1">{label}</p>
      <p className={`text-2xl font-black ${accentClass}`}>{value}</p>
    </div>
  )
}

/** Horizontal ranked bar list — single sequential hue for magnitude comparison. */
function HBarList({ data, maxItems = 7, emptyLabel = 'No data yet.' }) {
  const rows = useMemo(() => {
    const entries = Object.entries(data || {}).filter(([k]) => k)
    entries.sort((a, b) => b[1] - a[1])
    if (entries.length <= maxItems) return entries
    const head = entries.slice(0, maxItems - 1)
    const rest = entries.slice(maxItems - 1)
    const otherTotal = rest.reduce((sum, [, v]) => sum + v, 0)
    return [...head, ['Other', otherTotal]]
  }, [data, maxItems])

  if (rows.length === 0) {
    return <p className="text-xs text-brand-500 dark:text-brand-400">{emptyLabel}</p>
  }

  const max = Math.max(...rows.map(([, v]) => v), 1)

  return (
    <ul className="space-y-2">
      {rows.map(([key, count]) => (
        <li key={key} className="flex items-center gap-2 text-xs sm:text-sm">
          <span className="w-24 sm:w-28 flex-shrink-0 truncate text-brand-700 dark:text-brand-300 capitalize" title={key}>
            {key}
          </span>
          <span className={`relative flex-1 h-4 rounded ${TRACK} overflow-hidden`}>
            <span
              className={`absolute inset-y-0 left-0 rounded ${BAR_FILL}`}
              style={{ width: `${Math.max((count / max) * 100, 3)}%` }}
            />
          </span>
          <span className="w-10 flex-shrink-0 text-right font-medium text-brand-900 dark:text-brand-50 tabular-nums">
            {count}
          </span>
        </li>
      ))}
    </ul>
  )
}

/** Column chart of events per day with hover tooltip. */
function DailyActivityChart({ days }) {
  const [hovered, setHovered] = useState(null)
  const ordered = useMemo(() => [...(days || [])].sort((a, b) => a.date.localeCompare(b.date)), [days])

  if (ordered.length === 0) {
    return <p className="text-xs text-brand-500 dark:text-brand-400">No data yet.</p>
  }

  const max = Math.max(...ordered.map((d) => d.count), 1)

  return (
    <div className="relative">
      <div className={`flex items-end gap-1 h-40 border-b ${GRID}`}>
        {ordered.map((d, i) => (
          <div
            key={d.date}
            className="relative flex-1 h-full flex items-end justify-center group"
            onMouseEnter={() => setHovered(i)}
            onMouseLeave={() => setHovered((h) => (h === i ? null : h))}
          >
            {hovered === i && (
              <div className="absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap bg-brand-900 dark:bg-black text-white text-[10px] px-2 py-1 rounded shadow-lg z-10">
                {d.date}: {d.count}
              </div>
            )}
            <div
              className={`w-full max-w-[18px] rounded-t ${BAR_FILL} transition-opacity ${hovered !== null && hovered !== i ? 'opacity-50' : 'opacity-100'}`}
              style={{ height: `${Math.max((d.count / max) * 100, 2)}%` }}
            />
          </div>
        ))}
      </div>
      <div className="flex justify-between mt-1 text-[9px] text-brand-500 dark:text-brand-400">
        <span>{ordered[0].date}</span>
        {ordered.length > 1 && <span>{ordered[ordered.length - 1].date}</span>}
      </div>
    </div>
  )
}

function ExportButtons({ token, days }) {
  const [downloading, setDownloading] = useState(null)

  const download = async (format) => {
    setDownloading(format)
    try {
      const res = await fetch(`${API_BASE}/api/analytics/export?days=${days}&format=${format}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error('Export failed')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `feedback_${days}d.${format === 'jsonl' ? 'jsonl' : 'json'}`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch {
      // silently ignore; button just stops spinning
    } finally {
      setDownloading(null)
    }
  }

  return (
    <div className="flex gap-1.5">
      <button
        onClick={() => download('json')}
        disabled={downloading !== null}
        className="text-[11px] px-2 py-1 rounded-lg border border-brand-200 dark:border-white/10 text-brand-600 dark:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-700 disabled:opacity-50 transition-colors"
      >
        {downloading === 'json' ? 'Exporting...' : '⬇ JSON'}
      </button>
      <button
        onClick={() => download('jsonl')}
        disabled={downloading !== null}
        className="text-[11px] px-2 py-1 rounded-lg border border-brand-200 dark:border-white/10 text-brand-600 dark:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-700 disabled:opacity-50 transition-colors"
        title="JSON Lines — one record per line, common for RAG/eval pipelines"
      >
        {downloading === 'jsonl' ? 'Exporting...' : '⬇ JSONL'}
      </button>
    </div>
  )
}

function RecentErrorsList({ items }) {
  if (!items || items.length === 0) {
    return <p className="text-xs text-brand-500 dark:text-brand-400">No errors — clean run.</p>
  }
  return (
    <ul className="space-y-2 max-h-64 overflow-y-auto">
      {items.map((e, i) => (
        <li key={i} className="text-xs sm:text-sm border-b border-brand-100 dark:border-white/5 pb-2 last:border-0">
          <div className="flex items-center gap-2">
            <span className="text-[#d03b3b] font-mono text-[10px] px-1.5 py-0.5 rounded bg-[#d03b3b]/10">
              {e.metadata?.status_code || 'ERR'}
            </span>
            <span className="text-brand-700 dark:text-brand-300 font-medium truncate">{e.command}</span>
          </div>
          <p className="text-brand-500 dark:text-brand-400 line-clamp-1">{e.message}</p>
          <p className="text-[10px] text-brand-500 dark:text-brand-400">{new Date(e.timestamp).toLocaleString()}</p>
        </li>
      ))}
    </ul>
  )
}

function FeedbackList({ items }) {
  const [filter, setFilter] = useState('all')

  const filtered = (items || []).filter((f) => {
    if (filter === 'all') return true
    return f.feedback === filter
  })

  return (
    <div>
      <div className="flex gap-1 mb-3">
        {[
          ['all', 'All'],
          ['thumbs_up', '👍 Positive'],
          ['thumbs_down', '👎 Negative'],
        ].map(([value, label]) => (
          <button
            key={value}
            onClick={() => setFilter(value)}
            className={`text-[11px] px-2 py-1 rounded-lg border transition-colors ${
              filter === value
                ? 'bg-accent text-white border-accent'
                : 'border-brand-200 dark:border-white/10 text-brand-600 dark:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <p className="text-xs text-brand-500 dark:text-brand-400">No feedback yet.</p>
      ) : (
        <ul className="space-y-3 max-h-72 overflow-y-auto">
          {filtered.map((f, i) => (
            <li key={i} className="text-xs sm:text-sm border-b border-brand-100 dark:border-white/5 pb-2 last:border-0">
              <div className="flex items-start gap-2">
                <span
                  className={`mt-0.5 flex-shrink-0 ${
                    f.feedback === 'thumbs_up' ? 'text-[#0ca30c]' : 'text-[#d03b3b]'
                  }`}
                >
                  {f.feedback === 'thumbs_up' ? '👍' : '👎'}
                </span>
                <div className="min-w-0 flex-1">
                  {f.user_message && (
                    <p className="text-brand-500 dark:text-brand-400 italic line-clamp-1">
                      Asked: {f.user_message}
                    </p>
                  )}
                  <p className="text-brand-800 dark:text-brand-200 line-clamp-2">{f.message}</p>
                  <p className="text-[10px] text-brand-500 dark:text-brand-400">
                    {new Date(f.timestamp).toLocaleString()}
                  </p>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** Questions that were rated badly with nothing retrieved — an ingest list. */
function KnowledgeGapList({ items }) {
  if (!items?.length) {
    return (
      <p className="text-xs text-brand-500 dark:text-brand-400">
        No gaps recorded. These only appear when an answer is rated down and no
        knowledge was retrieved for it.
      </p>
    )
  }
  return (
    <div className="space-y-2 max-h-[420px] overflow-y-auto">
      {items.map((gap, i) => (
        <div key={i} className="p-2.5 rounded-lg bg-brand-50 dark:bg-brand-900/50 border border-brand-100 dark:border-white/5">
          <p className="text-xs font-medium text-brand-900 dark:text-brand-50 break-words">
            {gap.question}
          </p>
          {gap.keywords?.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {gap.keywords.map((kw) => (
                <span key={kw} className="px-1.5 py-0.5 rounded text-[10px] bg-brand-200/60 dark:bg-white/10 text-brand-600 dark:text-brand-300">
                  {kw}
                </span>
              ))}
            </div>
          )}
          <p className="mt-1 text-[10px] text-brand-400 dark:text-brand-500">
            {gap.timestamp?.slice(0, 16).replace('T', ' ')}
            {gap.language ? ` · ${gap.language}` : ''}
          </p>
        </div>
      ))}
    </div>
  )
}

/** Per-chunk ratings. Ratings recorded before chunk ids were logged are absent. */
function ChunkQualityList({ items }) {
  if (!items?.length) {
    return (
      <p className="text-xs text-brand-500 dark:text-brand-400">
        Nothing yet. Only ratings given after chunk ids started being logged can
        be attributed to a source.
      </p>
    )
  }
  return (
    <div className="space-y-1.5 max-h-[420px] overflow-y-auto">
      {items.map((chunk) => {
        // Score is share of positive ratings; colour marks the problem cases.
        const bad = chunk.score !== null && chunk.score < 0.5
        const good = chunk.score !== null && chunk.score >= 0.8
        return (
          <div key={chunk.chunk_id} className="flex items-center gap-2 p-2 rounded-lg bg-brand-50 dark:bg-brand-900/50 border border-brand-100 dark:border-white/5">
            <code className="text-[10px] font-mono text-brand-500 dark:text-brand-400 truncate flex-1 min-w-0">
              {chunk.chunk_id}
            </code>
            <span className="text-[10px] text-green-600 dark:text-green-400 shrink-0">↑{chunk.up}</span>
            <span className="text-[10px] text-red-500 dark:text-red-400 shrink-0">↓{chunk.down}</span>
            <span
              className={`text-[10px] font-bold w-9 text-right shrink-0 ${
                bad ? 'text-red-500' : good ? 'text-green-600 dark:text-green-400' : 'text-brand-500'
              }`}
            >
              {chunk.score === null ? '—' : `${Math.round(chunk.score * 100)}%`}
            </span>
          </div>
        )
      })}
    </div>
  )
}

function EvalCasesButton({ token, days, count }) {
  const [downloading, setDownloading] = useState(false)

  const download = async () => {
    setDownloading(true)
    try {
      const res = await fetch(`${API_BASE}/api/analytics/eval-cases?days=${days}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error('Download failed')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'eval_cases.json'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      // Surfaced by the disabled state returning; nothing else to do here.
    } finally {
      setDownloading(false)
    }
  }

  return (
    <button
      onClick={download}
      disabled={downloading || !count}
      className="text-xs px-3 py-1 rounded-lg bg-accent text-brand-950 font-bold hover:opacity-90 transition-opacity disabled:opacity-40"
    >
      {downloading ? 'Preparing…' : `Download ${count} cases`}
    </button>
  )
}

export default function AdminDashboard() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) || null)
  const [data, setData] = useState(null)
  const [learning, setLearning] = useState(null)
  const [error, setError] = useState(null)
  const [days, setDays] = useState(7)
  const [activeTab, setActiveTab] = useState('analytics')

  const handleLogin = (newToken) => setToken(newToken)
  const handleLogout = () => {
    localStorage.removeItem(TOKEN_KEY)
    setToken(null)
    setData(null)
    setLearning(null)
  }

  useEffect(() => {
    if (!token) return
    fetch(`${API_BASE}/api/analytics?days=${days}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (res.status === 401) {
          handleLogout()
          throw new Error('Token expired')
        }
        return res.ok ? res.json() : Promise.reject(new Error('Failed to load'))
      })
      .then(setData)
      .catch(setError)

    // Separate endpoint: the learning report aggregates differently and should
    // not delay or fail the main summary.
    fetch(`${API_BASE}/api/analytics/learning?days=${days}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then(setLearning)
      .catch(() => setLearning(null))
  }, [days, token])

  if (!token) return <LoginForm onLogin={handleLogin} />

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="text-center">
          <p className="text-red-500 mb-2">Could not load analytics.</p>
          <a href="/" className="text-accent hover:underline text-sm">Back to Chat</a>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <p className="text-brand-500">Loading...</p>
      </div>
    )
  }

  const thumbsUp = data.feedback_counts?.thumbs_up || 0
  const thumbsDown = data.feedback_counts?.thumbs_down || 0
  const feedbackTotal = thumbsUp + thumbsDown
  const satisfactionPct = feedbackTotal > 0 ? Math.round((thumbsUp / feedbackTotal) * 100) : null

  const ragCoverage = data.rag_coverage || {}
  const totalErrors = Object.values(data.error_counts || {}).reduce((a, b) => a + b, 0)

  const satisfactionFor = (bucket) => {
    const b = data.feedback_by_rag_context?.[bucket]
    if (!b) return null
    const up = b.thumbs_up || 0
    const down = b.thumbs_down || 0
    const total = up + down
    return total > 0 ? Math.round((up / total) * 100) : null
  }
  const satisfactionWithContext = satisfactionFor('with_context')
  const satisfactionNoContext = satisfactionFor('no_context')

  return (
    <div className="min-h-screen bg-brand-50 dark:bg-brand-900 text-brand-900 dark:text-brand-50 p-4 sm:p-6">
      <div className="max-w-6xl mx-auto">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-4">
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-black">Professor Pepe Admin</h1>
            <div className="flex bg-brand-100 dark:bg-white/5 rounded-lg p-1">
              <button
                onClick={() => setActiveTab('analytics')}
                className={`px-3 py-1 text-sm font-medium rounded-md transition-colors ${activeTab === 'analytics' ? 'bg-white dark:bg-brand-700 shadow-sm' : 'text-brand-500 hover:text-brand-900 dark:hover:text-brand-100'}`}
              >
                Analytics
              </button>
              <button
                onClick={() => setActiveTab('learning')}
                className={`px-3 py-1 text-sm font-medium rounded-md transition-colors ${activeTab === 'learning' ? 'bg-white dark:bg-brand-700 shadow-sm' : 'text-brand-500 hover:text-brand-900 dark:hover:text-brand-100'}`}
              >
                Learning
              </button>
              <button
                onClick={() => setActiveTab('art')}
                className={`px-3 py-1 text-sm font-medium rounded-md transition-colors ${activeTab === 'art' ? 'bg-white dark:bg-brand-700 shadow-sm' : 'text-brand-500 hover:text-brand-900 dark:hover:text-brand-100'}`}
              >
                Community Art
              </button>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {activeTab !== 'art' && (
              <select
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="bg-white dark:bg-brand-800 border border-brand-200 dark:border-white/10 rounded-lg px-3 py-1 text-sm"
              >
                <option value={1}>24 hours</option>
                <option value={7}>7 days</option>
                <option value={30}>30 days</option>
                <option value={90}>90 days</option>
              </select>
            )}
            <button
              onClick={handleLogout}
              className="text-sm px-3 py-1 bg-red-500 hover:bg-red-600 text-white rounded-lg transition-colors"
            >
              Logout
            </button>
            <a href="/" className="text-sm px-3 py-1 bg-accent hover:bg-accent/90 text-white rounded-lg transition-colors">
              Back to Chat
            </a>
          </div>
        </div>

        {activeTab === 'art' ? (
          <ArtApprovals token={token} />
        ) : activeTab === 'learning' ? (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-6">
              <StatTile label="Knowledge Gaps" value={learning?.knowledge_gaps?.length ?? '—'} />
              <StatTile label="Rated Chunks" value={learning?.chunk_quality?.length ?? '—'} />
              <StatTile
                label="Weak Chunks"
                value={
                  learning?.chunk_quality
                    ? learning.chunk_quality.filter((c) => c.score !== null && c.score < 0.5).length
                    : '—'
                }
                accentClass="text-red-500"
              />
              <StatTile label="Eval Cases" value={learning?.eval_cases_available ?? '—'} />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6 mb-6">
              <Card
                title="Knowledge Gaps"
                subtitle="Rated down with nothing retrieved — the knowledge base had no answer"
              >
                <KnowledgeGapList items={learning?.knowledge_gaps} />
              </Card>
              <Card
                title="Chunk Quality"
                subtitle="How answers using each chunk were rated"
              >
                <ChunkQualityList items={learning?.chunk_quality} />
              </Card>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
              <Card title="Why answers were rated down" subtitle="Reason given after a thumbs-down">
                <HBarList
                  data={learning?.feedback_reasons}
                  emptyLabel="No reasons given yet."
                />
              </Card>
              <Card
                title="Retrieval Eval Cases"
                subtitle="Built from thumbs-up answers, for measuring retrieval changes"
                action={
                  <EvalCasesButton
                    token={token}
                    days={days}
                    count={learning?.eval_cases_available || 0}
                  />
                }
              >
                <p className="text-xs text-brand-500 dark:text-brand-400">
                  A positively rated answer is evidence its chunks were the right
                  ones. Drop the file into{' '}
                  <code className="bg-brand-100 dark:bg-brand-700 px-1 rounded">
                    backend/rag/eval_cases.json
                  </code>{' '}
                  and run{' '}
                  <code className="bg-brand-100 dark:bg-brand-700 px-1 rounded">
                    scripts/eval_rag.py
                  </code>{' '}
                  to measure whether a change to chunking or retrieval actually
                  helped. The file shipped with empty labels, so it currently
                  measures nothing.
                </p>
              </Card>
            </div>

            <p className="mt-6 text-[11px] text-brand-500 dark:text-brand-400">
              This report is read-only by design. Ratings come from a public app
              and can be spammed, so nothing here changes how answers are
              generated on its own.
            </p>
          </>
        ) : (
          <>
            {/* KPI row */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 sm:gap-4 mb-6">
          <StatTile label="Total Events" value={data.total_events} />
          <StatTile label="Unique Sessions" value={data.unique_sessions} />
          <StatTile
            label="Satisfaction"
            value={satisfactionPct !== null ? `${satisfactionPct}%` : '—'}
            accentClass={
              satisfactionPct === null
                ? undefined
                : satisfactionPct >= 60
                ? 'text-[#0ca30c]'
                : 'text-[#d03b3b]'
            }
          />
          <StatTile
            label="RAG Coverage"
            value={ragCoverage.coverage_pct !== null && ragCoverage.coverage_pct !== undefined ? `${ragCoverage.coverage_pct}%` : '—'}
            accentClass={
              ragCoverage.coverage_pct === null || ragCoverage.coverage_pct === undefined
                ? undefined
                : ragCoverage.coverage_pct >= 60
                ? 'text-[#0ca30c]'
                : 'text-[#fab219]'
            }
          />
          <StatTile label="Avg Latency" value={data.avg_latency_ms ? `${data.avg_latency_ms}ms` : '—'} />
        </div>

        {/* Activity over time */}
        <div className="mb-6">
          <Card title="Daily Activity" subtitle="Events per day">
            <DailyActivityChart days={data.daily_events} />
          </Card>
        </div>

        {/* Rankings — what are users doing */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          <Card title="Commands" subtitle="Most used first">
            <HBarList data={data.command_counts} />
          </Card>
          <Card title="Languages" subtitle="Detected client language">
            <HBarList data={data.language_counts} />
          </Card>
          <Card title="Top Topics" subtitle="Keywords in user messages">
            <HBarList data={Object.fromEntries((data.top_topics || []).map((t) => [t.keyword, t.count]))} />
          </Card>
          <Card title="Countries" subtitle="By Cloudflare geo header">
            <HBarList data={data.country_counts} />
          </Card>
          <Card title="Devices" subtitle="Mobile vs desktop">
            <HBarList data={data.device_counts} />
          </Card>
          <Card title="Operating Systems">
            <HBarList data={data.os_counts} />
          </Card>
          <Card title="Conversions" subtitle="Support / Discord / faucet / wallet clicks">
            <HBarList data={data.conversion_counts} />
          </Card>
        </div>

        {/* Feedback — what users liked or didn't */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
          <Card title="Feedback Breakdown" className="lg:col-span-1">
            <ul className="space-y-2">
              <li className="flex justify-between text-sm">
                <span className="text-[#0ca30c] font-medium">👍 Positive</span>
                <span className="font-bold tabular-nums">{thumbsUp}</span>
              </li>
              <li className="flex justify-between text-sm">
                <span className="text-[#d03b3b] font-medium">👎 Negative</span>
                <span className="font-bold tabular-nums">{thumbsDown}</span>
              </li>
            </ul>
          </Card>
          <Card
            title="Recent Feedback"
            subtitle="Which responses users liked or disliked"
            className="lg:col-span-2"
            action={<ExportButtons token={token} days={days} />}
          >
            <FeedbackList items={data.recent_feedback} />
          </Card>
        </div>

        {/* RAG quality — does having knowledge-base context actually help? */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
          <Card title="Knowledge Base Coverage" subtitle="Share of questions answered with Qdrant context">
            <ul className="space-y-2">
              <li className="flex justify-between text-sm">
                <span className="text-brand-700 dark:text-brand-300">With context</span>
                <span className="font-bold tabular-nums">{ragCoverage.with_context ?? 0}</span>
              </li>
              <li className="flex justify-between text-sm">
                <span className="text-brand-700 dark:text-brand-300">No context found</span>
                <span className="font-bold tabular-nums">{ragCoverage.no_context ?? 0}</span>
              </li>
            </ul>
          </Card>
          <Card title="Satisfaction by Context" subtitle="Does missing context hurt ratings?">
            <ul className="space-y-2">
              <li className="flex justify-between text-sm">
                <span className="text-brand-700 dark:text-brand-300">With context</span>
                <span className="font-bold tabular-nums">
                  {satisfactionWithContext !== null ? `${satisfactionWithContext}%` : '—'}
                </span>
              </li>
              <li className="flex justify-between text-sm">
                <span className="text-brand-700 dark:text-brand-300">No context</span>
                <span className="font-bold tabular-nums">
                  {satisfactionNoContext !== null ? `${satisfactionNoContext}%` : '—'}
                </span>
              </li>
            </ul>
          </Card>
        </div>

        {/* Errors — what's breaking for users */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
          <Card title="Errors by Endpoint" subtitle={`${totalErrors} total in range`} className="lg:col-span-1">
            <HBarList data={data.error_counts} emptyLabel="No errors — clean run." />
          </Card>
          <Card title="Recent Errors" className="lg:col-span-2">
            <RecentErrorsList items={data.recent_errors} />
          </Card>
        </div>
          </>
        )}
      </div>
    </div>
  )
}
