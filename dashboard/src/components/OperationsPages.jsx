import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api/client.js'

const SUGGESTIONS = [
  'RAG mimarisi nasıl çalışır?',
  'Doküman yükleme limitleri nelerdir?',
  'Son güncellenen izin dokümanları neler?',
  'KVKK kapsamında hangi politika maddeleri geçerli?',
]

const EMPTY_SUMMARY = {
  documents: { total: 0, ready: 0, processing: 0, failed: 0 },
  collections: { total: 0, top: [] },
  queries: { total: 0, last_7_days: 0, avg_query_time_ms: 0 },
  accuracy: { average: null },
  recent_activity: [],
}

function formatDate(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString('tr-TR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}

function fileType(filename, fallback) {
  return (fallback || filename?.split('.').pop() || 'file').toUpperCase()
}

function statusLabel(status) {
  const labels = {
    ready: 'Processed',
    completed: 'Completed',
    processing: 'Processing',
    pending: 'Pending',
    failed: 'Failed',
    error: 'Failed',
    queued: 'Queued',
    running: 'Running',
    ok: 'Healthy',
    degraded: 'Degraded',
    stopped: 'Stopped',
    not_configured: 'Not Configured',
  }
  return labels[status] || status || 'Unknown'
}

function StatusBadge({ status }) {
  const tone = ['ready', 'completed', 'ok', 'healthy', 'running'].includes(status)
    ? 'success'
    : ['failed', 'error', 'stopped'].includes(status)
      ? 'danger'
      : 'warning'
  return <span className={`status-badge ${tone}`}>{statusLabel(status)}</span>
}

function GlassCard({ className = '', children }) {
  return <section className={`glass-card ${className}`}>{children}</section>
}

function PageHeader({ eyebrow, title, description, action }) {
  return (
    <div className="page-header">
      <div>
        {eyebrow && <span className="page-eyebrow">{eyebrow}</span>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {action && <div className="page-action">{action}</div>}
    </div>
  )
}

function StatCard({ icon, label, value, delta, tone = 'blue' }) {
  return (
    <GlassCard className={`stat-card tone-${tone}`}>
      <span className="stat-icon">{icon}</span>
      <span>{label}</span>
      <strong>{value}</strong>
      {delta && <small>{delta}</small>}
    </GlassCard>
  )
}

function EmptyState({ title, detail }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      {detail && <span>{detail}</span>}
    </div>
  )
}

function MiniLineChart({ points = [] }) {
  const values = points.length ? points : [18, 22, 19, 30, 26, 38, 32, 45, 42, 58, 51, 64]
  const max = Math.max(...values, 1)
  const coords = values.map((value, index) => {
    const x = (index / Math.max(values.length - 1, 1)) * 100
    const y = 100 - (value / max) * 86 - 7
    return `${x},${y}`
  }).join(' ')
  return (
    <svg className="mini-chart" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={coords} />
      <polygon points={`0,100 ${coords} 100,100`} />
    </svg>
  )
}

function DonutChart({ total = 0, segments = [] }) {
  const safeTotal = Math.max(total, segments.reduce((sum, item) => sum + item.value, 0), 1)
  let offset = 25
  return (
    <div className="donut-wrap">
      <svg viewBox="0 0 42 42" className="donut-chart" aria-hidden="true">
        <circle cx="21" cy="21" r="15.9" className="donut-bg" />
        {segments.map((segment) => {
          const dash = (segment.value / safeTotal) * 100
          const circle = (
            <circle
              key={segment.label}
              cx="21"
              cy="21"
              r="15.9"
              className="donut-segment"
              stroke={segment.color}
              strokeDasharray={`${dash} ${100 - dash}`}
              strokeDashoffset={offset}
            />
          )
          offset -= dash
          return circle
        })}
      </svg>
      <div>
        <strong>{total}</strong>
        <span>Total Queries</span>
      </div>
    </div>
  )
}

function useAsyncData(loader, deps = []) {
  const [state, setState] = useState({ loading: true, error: '', data: null })
  const load = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: '' }))
    try {
      const data = await loader()
      setState({ loading: false, error: '', data })
    } catch (error) {
      setState({ loading: false, error: error.message, data: null })
    }
  }, deps) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { load() }, [load])
  return { ...state, reload: load }
}

export function DashboardPage({ tenant, onNavigate }) {
  const { data, loading, error, reload } = useAsyncData(async () => {
    const [summary, health] = await Promise.all([
      api.getDashboardSummary().catch(() => EMPTY_SUMMARY),
      api.health().catch(() => null),
    ])
    return { summary: summary || EMPTY_SUMMARY, health }
  }, [])

  const summary = data?.summary || EMPTY_SUMMARY
  const health = data?.health
  const accuracy = summary.accuracy?.average == null ? 'N/A' : `${summary.accuracy.average}%`

  return (
    <div className="page-stack dashboard-page">
      <PageHeader
        eyebrow="Private knowledge console"
        title={`Welcome back, ${tenant?.name || 'TurkRAG'}`}
        description="Secure Turkish enterprise document intelligence, retrieval, ingestion, and quality monitoring in one workspace."
        action={<button className="primary-action" type="button" onClick={reload}>{loading ? 'Refreshing' : 'Refresh'}</button>}
      />

      {error && <div className="inline-error">{error}</div>}

      <div className="dashboard-hero">
        <div className="hero-copy">
          <span className="page-eyebrow">AI-Powered Document Intelligence</span>
          <h2>Ask trusted questions across tenant-scoped company knowledge.</h2>
          <p>Hybrid retrieval, Turkish language handling, ACL-aware documents, and citation-first answers.</p>
        </div>
        <div className="orbital-visual" aria-hidden="true">
          <span /><span /><span /><i />
        </div>
      </div>

      <div className="stats-grid">
        <StatCard icon="▣" label="Documents" value={summary.documents.total} delta={`+${summary.documents.ready} ready`} />
        <StatCard icon="◈" label="Collections" value={summary.collections.total} delta="tenant scoped" tone="cyan" />
        <StatCard icon="?" label="Questions" value={summary.queries.total} delta={`+${summary.queries.last_7_days} this week`} tone="purple" />
        <StatCard icon="✓" label="Avg. Accuracy" value={accuracy} delta={summary.accuracy?.status || 'eval pending'} tone="green" />
      </div>

      <div className="dashboard-grid">
        <GlassCard className="ask-preview">
          <div className="card-head">
            <div>
              <span>Ask Documents</span>
              <strong>Query your private knowledge base</strong>
            </div>
            <button type="button" onClick={() => onNavigate('chat')}>Open</button>
          </div>
          <button className="ask-input-preview" type="button" onClick={() => onNavigate('chat')}>
            Ask anything about your documents...
            <span>↗</span>
          </button>
          <div className="suggested-row">
            {SUGGESTIONS.map((item) => <button key={item} type="button" onClick={() => onNavigate('chat')}>{item}</button>)}
          </div>
        </GlassCard>

        <GlassCard>
          <div className="card-head">
            <div>
              <span>System Status</span>
              <strong>{health?.status === 'ok' ? 'All systems operational' : 'Dependency check'}</strong>
            </div>
            <StatusBadge status={health?.status || 'pending'} />
          </div>
          <div className="status-grid">
            <span>API <StatusBadge status={health?.status || 'pending'} /></span>
            <span>Database <StatusBadge status={health?.postgres || 'pending'} /></span>
            <span>Vector DB <StatusBadge status={health?.qdrant || 'pending'} /></span>
            <span>Worker <StatusBadge status={health?.worker || 'pending'} /></span>
          </div>
        </GlassCard>
      </div>

      <div className="dashboard-grid lower">
        <GlassCard>
          <div className="card-head">
            <div><span>Collections</span><strong>Knowledge spaces</strong></div>
            <button type="button" onClick={() => onNavigate('collections')}>Manage</button>
          </div>
          <div className="collection-strip">
            {summary.collections.top?.length ? summary.collections.top.map((collection) => (
              <div className="collection-mini" key={collection.id}>
                <i style={{ background: collection.color }} />
                <strong>{collection.name}</strong>
                <span>{collection.document_count} docs · {collection.ready_count} ready</span>
              </div>
            )) : <EmptyState title="No collections yet" detail="Create collections to organize documents." />}
          </div>
        </GlassCard>

        <GlassCard>
          <div className="card-head">
            <div><span>Recent Activity</span><strong>Latest operations</strong></div>
          </div>
          <div className="activity-list">
            {summary.recent_activity?.length ? summary.recent_activity.map((item) => (
              <div key={`${item.type}-${item.id}`} className="activity-row">
                <span>{item.type === 'job' ? 'JOB' : 'DOC'}</span>
                <strong>{item.title}</strong>
                <StatusBadge status={item.status} />
                <small>{formatDate(item.created_at)}</small>
              </div>
            )) : <EmptyState title="No activity" detail="Uploads and ingestion jobs will appear here." />}
          </div>
        </GlassCard>
      </div>
    </div>
  )
}

export function DocumentsPage() {
  const fileInput = useRef(null)
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('all')
  const [collectionId, setCollectionId] = useState('')
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState('')
  const { data, loading, error, reload } = useAsyncData(async () => {
    const [documents, collections] = await Promise.all([api.listDocuments(), api.listCollections().catch(() => [])])
    return { documents: documents || [], collections: collections || [] }
  }, [])
  const docs = data?.documents || []
  const collections = data?.collections || []
  const filtered = docs.filter((doc) => {
    const matchesText = !query || doc.filename.toLowerCase().includes(query.toLowerCase())
    const matchesStatus = status === 'all' || doc.status === status
    return matchesText && matchesStatus
  })

  const upload = async (files) => {
    if (!files?.length) return
    setUploading(true)
    setMessage('')
    try {
      for (const file of files) await api.uploadDocument(file, collectionId)
      setMessage('Document queued for ingestion.')
      await reload()
    } catch (err) {
      setMessage(err.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Document Library"
        title="Documents"
        description="Browse, upload, filter, and monitor tenant-scoped source material."
        action={<button className="primary-action" type="button" onClick={() => fileInput.current?.click()}>{uploading ? 'Uploading...' : '+ Upload Document'}</button>}
      />
      <input ref={fileInput} type="file" multiple hidden accept=".pdf,.docx,.txt,.xlsx,.xls,.csv" onChange={(event) => upload(event.target.files)} />

      <GlassCard>
        <div className="library-toolbar">
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search documents..." />
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="all">All status</option>
            <option value="ready">Processed</option>
            <option value="processing">Processing</option>
            <option value="failed">Failed</option>
            <option value="error">Error</option>
          </select>
          <select value={collectionId} onChange={(event) => setCollectionId(event.target.value)}>
            <option value="">No upload collection</option>
            {collections.map((collection) => <option key={collection.id} value={collection.id}>{collection.name}</option>)}
          </select>
          <button type="button" onClick={reload}>Refresh</button>
        </div>
        {message && <div className="inline-note">{message}</div>}
        {error && <div className="inline-error">{error}</div>}
        {loading ? <EmptyState title="Loading documents" /> : filtered.length ? (
          <div className="data-table document-table">
            <div className="table-head">
              <span>Document</span><span>Collection</span><span>Type</span><span>Chunks</span><span>Uploaded</span><span>Status</span>
            </div>
            {filtered.map((doc) => (
              <div className="table-row" key={doc.id}>
                <strong>{doc.filename}</strong>
                <span>{doc.collection_name || 'Unassigned'}</span>
                <span className="file-pill">{fileType(doc.filename, doc.file_type)}</span>
                <span>{doc.chunk_count ?? '-'}</span>
                <span>{formatDate(doc.created_at)}</span>
                <StatusBadge status={doc.status} />
              </div>
            ))}
          </div>
        ) : <EmptyState title="No matching documents" detail="Upload or adjust filters to see source records." />}
      </GlassCard>
    </div>
  )
}

export function CollectionsPage() {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [message, setMessage] = useState('')
  const { data, loading, error, reload } = useAsyncData(async () => api.listCollections(), [])
  const collections = data || []

  const create = async (event) => {
    event.preventDefault()
    if (!name.trim()) return
    setMessage('')
    try {
      await api.createCollection({ name: name.trim(), description: description.trim() || null })
      setName('')
      setDescription('')
      setMessage('Collection created.')
      await reload()
    } catch (err) {
      setMessage(err.message)
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Knowledge Spaces"
        title="Collections"
        description="Organize documents into operational knowledge areas."
      />

      <div className="collections-layout">
        <GlassCard className="collection-create">
          <div className="card-head"><div><span>Create</span><strong>New collection</strong></div></div>
          <form onSubmit={create} className="stack-form">
            <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Collection name" />
            <textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Short description" rows={4} />
            <button className="primary-action" type="submit">Create Collection</button>
          </form>
          {message && <div className="inline-note">{message}</div>}
        </GlassCard>

        <div className="collection-grid">
          {error && <div className="inline-error">{error}</div>}
          {loading ? <EmptyState title="Loading collections" /> : collections.length ? collections.map((collection) => {
            const progress = collection.document_count ? Math.round((collection.ready_count / collection.document_count) * 100) : 0
            return (
              <GlassCard className="collection-card" key={collection.id}>
                <div className="collection-icon" style={{ background: collection.color }}>▣</div>
                <div className="card-menu">•••</div>
                <h3>{collection.name}</h3>
                <p>{collection.description || 'Tenant-scoped document collection'}</p>
                <div className="collection-meter"><span style={{ width: `${progress}%`, background: collection.color }} /></div>
                <div className="collection-meta">
                  <span>{collection.document_count} documents</span>
                  <strong>{collection.ready_count} ready</strong>
                </div>
              </GlassCard>
            )
          }) : <EmptyState title="No collections" detail="Create a collection to group documents." />}
        </div>
      </div>
    </div>
  )
}

export function HistoryPage() {
  const [selected, setSelected] = useState(null)
  const [messages, setMessages] = useState([])
  const [query, setQuery] = useState('')
  const { data, loading, error } = useAsyncData(async () => api.listSessions(50), [])
  const sessions = (data || []).filter((session) => !query || session.preview.toLowerCase().includes(query.toLowerCase()))

  useEffect(() => {
    if (!selected && sessions.length) setSelected(sessions[0].id)
  }, [sessions, selected])

  useEffect(() => {
    if (!selected) return
    api.getSessionMessages(selected).then(setMessages).catch(() => setMessages([]))
  }, [selected])

  const question = messages.find((message) => message.role === 'user')
  const answer = [...messages].reverse().find((message) => message.role === 'assistant')

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Conversation Archive" title="History" description="Review past questions, answers, and cited sources." />
      <div className="history-layout">
        <GlassCard className="history-list">
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search history..." />
          {error && <div className="inline-error">{error}</div>}
          {loading ? <EmptyState title="Loading history" /> : sessions.map((session) => (
            <button key={session.id} className={selected === session.id ? 'active' : ''} type="button" onClick={() => setSelected(session.id)}>
              <strong>{session.preview}</strong>
              <span>{formatDate(session.created_at)} · {session.message_count} messages</span>
            </button>
          ))}
        </GlassCard>
        <GlassCard className="history-detail">
          {selected ? (
            <>
              <span className="page-eyebrow">Selected conversation</span>
              <h2>{question?.content || 'Empty session'}</h2>
              <p>{answer?.content || 'No answer saved for this session.'}</p>
              <div className="source-list-inline">
                {(answer?.citations || []).map((citation, index) => (
                  <div key={`${citation.filename}-${index}`} className="source-chip-card">
                    <strong>{citation.filename}</strong>
                    <span>Chunk {citation.chunk_index} · {citation.score == null ? 'score n/a' : Math.round(citation.score * 100) + '%'}</span>
                  </div>
                ))}
              </div>
            </>
          ) : <EmptyState title="No session selected" />}
        </GlassCard>
      </div>
    </div>
  )
}

export function AnalyticsPage() {
  const { data, loading, error, reload } = useAsyncData(async () => {
    const [stats, recent, collections] = await Promise.all([
      api.getStats(),
      api.getRecentQueries(30),
      api.listCollections().catch(() => []),
    ])
    return { stats, recent, collections }
  }, [])
  const stats = data?.stats || {}
  const recent = data?.recent || []
  const collections = data?.collections || []
  const totalCollectionDocs = collections.reduce((sum, item) => sum + item.document_count, 0)

  return (
    <div className="page-stack analytics-page">
      <PageHeader
        eyebrow="Operational Metrics"
        title="Analytics"
        description="Query volume, retrieval speed, collection usage, and quality signals."
        action={<button className="primary-action" type="button" onClick={reload}>{loading ? 'Loading' : 'Refresh'}</button>}
      />
      {error && <div className="inline-error">{error}</div>}
      <div className="stats-grid">
        <StatCard icon="Σ" label="Total Queries" value={stats.total_queries ?? 0} delta="all time" />
        <StatCard icon="↯" label="Avg. Latency" value={`${stats.avg_query_time_ms ?? 0}ms`} delta="query time" tone="cyan" />
        <StatCard icon="24" label="Today" value={stats.queries_today ?? 0} delta="last 24h" tone="green" />
        <StatCard icon="▣" label="Collections" value={collections.length} delta={`${totalCollectionDocs} documents`} tone="purple" />
      </div>
      <div className="analytics-grid">
        <GlassCard className="chart-card wide">
          <div className="card-head"><div><span>Queries Over Time</span><strong>Recent activity trend</strong></div></div>
          <MiniLineChart points={recent.slice(0, 14).map((item, index) => (item.num_citations || 1) * 20 + index * 4)} />
        </GlassCard>
        <GlassCard className="chart-card">
          <div className="card-head"><div><span>Top Collections</span><strong>Document distribution</strong></div></div>
          <DonutChart
            total={stats.total_queries ?? 0}
            segments={collections.slice(0, 5).map((collection) => ({
              label: collection.name,
              value: Math.max(collection.document_count, 1),
              color: collection.color,
            }))}
          />
        </GlassCard>
        <GlassCard className="wide">
          <div className="card-head"><div><span>Recent Queries</span><strong>{recent.length} records</strong></div></div>
          <div className="data-table recent-query-table">
            <div className="table-head"><span>Query</span><span>Citations</span><span>Latency</span><span>Time</span></div>
            {recent.map((row) => (
              <div className="table-row" key={row.id}>
                <strong>{row.query}</strong>
                <span>{row.num_citations ?? 0}</span>
                <span>{row.query_time_ms ?? 0}ms</span>
                <span>{formatDate(row.created_at)}</span>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>
    </div>
  )
}

export function JobsPage() {
  const [tab, setTab] = useState('all')
  const { data, loading, error, reload } = useAsyncData(async () => api.listJobs(80), [])
  const jobs = data || []
  const filtered = jobs.filter((job) => tab === 'all' || job.status === tab)

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Queue Monitor"
        title="Ingestion Jobs"
        description="Monitor document parsing, chunking, embedding, retries, and worker heartbeats."
        action={<button className="primary-action" type="button" onClick={reload}>{loading ? 'Refreshing' : 'Refresh'}</button>}
      />
      <GlassCard>
        <div className="tabs-row">
          {['all', 'processing', 'completed', 'failed'].map((item) => (
            <button key={item} className={tab === item ? 'active' : ''} type="button" onClick={() => setTab(item)}>{item}</button>
          ))}
        </div>
        {error && <div className="inline-error">{error}</div>}
        {filtered.length ? (
          <div className="data-table jobs-table">
            <div className="table-head"><span>Job ID</span><span>Document</span><span>Status</span><span>Progress</span><span>Started</span><span>Heartbeat</span></div>
            {filtered.map((job) => {
              const progress = job.status === 'completed' ? 100 : job.status === 'processing' ? 66 : job.status === 'failed' ? 0 : 20
              return (
                <div className="table-row" key={job.id}>
                  <code>{job.id.slice(0, 8)}</code>
                  <strong>{job.filename}</strong>
                  <StatusBadge status={job.status} />
                  <span className="progress-cell"><i style={{ width: `${progress}%` }} />{progress}%</span>
                  <span>{formatDate(job.started_at || job.created_at)}</span>
                  <span>{formatDate(job.last_heartbeat_at)}</span>
                </div>
              )
            })}
          </div>
        ) : <EmptyState title={loading ? 'Loading jobs' : 'No jobs'} detail="Ingestion activity will appear here." />}
      </GlassCard>
    </div>
  )
}

export function SettingsPage({ theme, onThemeChange }) {
  const [settings, setSettings] = useState(null)
  const [message, setMessage] = useState('')
  const { data, loading, error, reload } = useAsyncData(async () => api.getUiSettings().catch(() => null), [])

  useEffect(() => {
    if (data) setSettings(data)
  }, [data])

  const update = (patch) => setSettings((prev) => ({ ...(prev || {}), ...patch }))
  const save = async () => {
    if (!settings) return
    setMessage('')
    try {
      const saved = await api.updateUiSettings(settings)
      setSettings(saved)
      if (settings.theme && settings.theme !== 'system') onThemeChange(settings.theme)
      setMessage('Settings saved.')
      await reload()
    } catch (err) {
      setMessage(err.message)
    }
  }

  const current = settings || {
    default_model: 'turkrag-model',
    default_language: 'tr',
    hybrid_search: true,
    results_per_page: 10,
    notifications_enabled: true,
    theme,
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Preferences"
        title="Settings"
        description="Safe dashboard preferences. Runtime model and security settings remain backend-controlled."
        action={<button className="primary-action" type="button" onClick={save} disabled={loading}>Save Changes</button>}
      />
      {error && <div className="inline-error">{error}</div>}
      {message && <div className="inline-note">{message}</div>}
      <GlassCard className="settings-panel">
        <div className="settings-section">
          <h3>General Settings</h3>
          <label>System Language<select value={current.default_language} onChange={(event) => update({ default_language: event.target.value })}><option value="tr">Türkçe</option><option value="en">English</option><option value="auto">Auto</option></select></label>
          <label>Default Model<input value={current.default_model} onChange={(event) => update({ default_model: event.target.value })} /></label>
          <label>Results per page<select value={current.results_per_page} onChange={(event) => update({ results_per_page: Number(event.target.value) })}><option value="10">10</option><option value="20">20</option><option value="50">50</option></select></label>
        </div>
        <div className="settings-section">
          <h3>Search</h3>
          <label className="switch-row">Hybrid Search<input type="checkbox" checked={current.hybrid_search} onChange={(event) => update({ hybrid_search: event.target.checked })} /><span /></label>
          <label className="switch-row">Notifications<input type="checkbox" checked={current.notifications_enabled} onChange={(event) => update({ notifications_enabled: event.target.checked })} /><span /></label>
          <div className="theme-options">
            {['light', 'dark', 'system'].map((item) => (
              <button key={item} type="button" className={current.theme === item ? 'active' : ''} onClick={() => update({ theme: item })}>{item}</button>
            ))}
          </div>
        </div>
      </GlassCard>
    </div>
  )
}

export function SystemPage() {
  const { data, loading, error, reload } = useAsyncData(async () => api.health(), [])
  const health = data
  const services = [
    ['API Service', health?.status],
    ['Database', health?.postgres],
    ['Vector Database', health?.qdrant],
    ['Redis / Cache', health?.redis],
    ['Document Worker', health?.worker],
    ['LLM Runtime', health?.llm_available ? 'ok' : 'degraded'],
  ]

  return (
    <div className="page-stack system-page">
      <PageHeader
        eyebrow="System / About"
        title="TurkRAG"
        description="Advanced RAG system with hybrid search, multi-tenancy, ACL-aware documents, and real-time processing."
        action={<button className="primary-action" type="button" onClick={reload}>{loading ? 'Checking' : 'Run Check'}</button>}
      />
      {error && <div className="inline-error">{error}</div>}
      <div className="system-hero">
        <div>
          <span className="page-eyebrow">AI-Powered Document Intelligence</span>
          <h2>Secure document intelligence console</h2>
          <p>Version {health?.version || '1.0.0'} · Uptime {health?.uptime_seconds ? `${health.uptime_seconds}s` : '-'}</p>
        </div>
        <div className="orbital-visual small" aria-hidden="true"><span /><span /><span /><i /></div>
      </div>
      <div className="service-grid">
        {services.map(([label, status]) => (
          <GlassCard key={label} className="service-card">
            <span>{label}</span>
            <StatusBadge status={status || 'pending'} />
          </GlassCard>
        ))}
      </div>
      <GlassCard>
        <div className="link-row">
          <a href="https://github.com/barisparlakk/TurkRAG" target="_blank" rel="noreferrer">GitHub Repository</a>
          <a href="/docs" target="_blank" rel="noreferrer">API Docs</a>
          <a href="/health" target="_blank" rel="noreferrer">Health JSON</a>
        </div>
      </GlassCard>
    </div>
  )
}
