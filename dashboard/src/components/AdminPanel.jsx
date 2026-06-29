import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client.js'

const IconCheck = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12"/>
  </svg>
)
const IconX = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
  </svg>
)
const IconRefresh = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.25"/>
  </svg>
)

function statusTone(status) {
  if (['ok', 'ready', 'completed', 'active', true].includes(status)) return 'ok'
  if (['queued', 'running', 'processing', 'pending'].includes(status)) return 'watch'
  return 'bad'
}

function StatusPill({ ok, label }) {
  return (
    <span className={`ops-status ${ok ? 'ok' : 'bad'}`}>
      {ok ? <IconCheck /> : <IconX />}
      {label}
    </span>
  )
}

function PanelTitle({ title, meta, action }) {
  return (
    <div className="ops-panel-head">
      <span>{title}</span>
      {action || <strong>{meta}</strong>}
    </div>
  )
}

function fmtDate(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('tr-TR', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function HealthSection({ health }) {
  if (!health) return (
    <section className="ops-panel">
      <PanelTitle title="Sistem durumu" meta="bekleniyor" />
      <div className="ops-empty compact">Health bilgisi alınamadı</div>
    </section>
  )

  return (
    <section className="ops-panel">
      <PanelTitle title="Sistem durumu" meta={health.version ? `v${health.version}` : 'canlı'} />
      <div className="health-matrix">
        <StatusPill ok={health.status === 'ok'} label="API" />
        <StatusPill ok={health.qdrant === 'ok'} label="Qdrant" />
        <StatusPill ok={health.postgres === 'ok'} label="PostgreSQL" />
        <StatusPill ok={Boolean(health.llm_available)} label="LLM" />
      </div>
    </section>
  )
}

function TenantSection({ onCreated }) {
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
  const [tenants, setTenants] = useState([])

  useEffect(() => {
    api.listTenants().then(setTenants).catch(() => {})
  }, [success])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim() || !slug.trim()) return
    setLoading(true); setError(null); setSuccess(null)
    try {
      await api.createTenant(name.trim(), slug.trim().toLowerCase())
      setSuccess(`"${slug}" kiracısı oluşturuldu`)
      setName(''); setSlug('')
      onCreated?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleNameChange = (val) => {
    setName(val)
    setSlug(val.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, ''))
  }

  return (
    <section className="ops-panel">
      <PanelTitle title="Tenant defteri" meta={`${tenants.length} tenant`} />

      {tenants.length > 0 && (
        <div className="tenant-register">
          {tenants.map((t, index) => (
            <div key={t.id} className="tenant-record">
              <code>T{String(index + 1).padStart(2, '0')}</code>
              <span>{t.name}</span>
              <small>{t.slug}</small>
            </div>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} className="ops-form-row">
        <input
          type="text"
          placeholder="Kiracı adı"
          value={name}
          onChange={(e) => handleNameChange(e.target.value)}
          className="input-field"
          required
        />
        <input
          type="text"
          placeholder="slug"
          value={slug}
          onChange={(e) => setSlug(e.target.value)}
          className="input-field mono"
          required
        />
        <button
          type="submit"
          disabled={loading || !name.trim() || !slug.trim()}
          className="btn btn-primary"
        >
          {loading ? '...' : 'Oluştur'}
        </button>
      </form>

      {error && <div className="ops-alert error">{error}</div>}
      {success && <div className="ops-alert success">{success}</div>}
    </section>
  )
}

function DocumentsSection() {
  const [docs, setDocs] = useState([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try { setDocs(await api.listDocuments()) } catch { }
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <section className="ops-panel">
      <PanelTitle
        title="Kaynak erişim kaydı"
        action={<button onClick={load} disabled={loading} className="btn btn-outline tight"><IconRefresh /> Yenile</button>}
      />
      {loading ? (
        <div className="ops-empty compact">Belgeler yükleniyor</div>
      ) : docs.length === 0 ? (
        <div className="ops-empty compact">Belge yok</div>
      ) : (
        <div className="ops-table docs-admin-table">
          <div className="ops-table-head">
            <span>Dosya</span><span>Durum</span><span>Parça</span><span>Tarih</span>
          </div>
          {docs.map((doc) => (
            <div className="ops-table-row" key={doc.id}>
              <span className="ops-table-primary">{doc.filename}</span>
              <span className={`ops-status ${statusTone(doc.status)}`}>{doc.status === 'ready' ? 'Hazır' : doc.status}</span>
              <span>{doc.chunk_count ?? '-'}</span>
              <span>{fmtDate(doc.created_at)}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function UserSection() {
  const [users, setUsers] = useState([])
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('member')
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setUsers(await api.listUsers())
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const create = async (e) => {
    e.preventDefault()
    setMessage(''); setError('')
    try {
      await api.createUser(email.trim(), password, role)
      setEmail(''); setPassword(''); setRole('member')
      setMessage('Kullanıcı oluşturuldu')
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  const update = async (user, patch) => {
    setMessage(''); setError('')
    try {
      await api.updateUser(user.id, patch)
      setMessage('Kullanıcı güncellendi')
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <section className="ops-panel">
      <PanelTitle title="Kullanıcı ve rol defteri" meta={`${users.length} kullanıcı`} />
      <form onSubmit={create} className="ops-form-row user-form">
        <input className="input-field" type="email" placeholder="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input className="input-field" type="password" placeholder="ilk şifre" value={password} onChange={(e) => setPassword(e.target.value)} />
        <select className="input-field" value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="member">member</option>
          <option value="admin">admin</option>
        </select>
        <button className="btn btn-primary" disabled={!email.trim() || password.length < 8}>Ekle</button>
      </form>
      {message && <div className="ops-alert success">{message}</div>}
      {error && <div className="ops-alert error">{error}</div>}

      <div className="ops-table user-admin-table">
        <div className="ops-table-head">
          <span>Email</span><span>Rol</span><span>Durum</span><span>İşlem</span>
        </div>
        {loading ? (
          <div className="ops-empty compact">Yükleniyor</div>
        ) : users.length === 0 ? (
          <div className="ops-empty compact">Kullanıcı yok</div>
        ) : users.map((u) => (
          <div className="ops-table-row" key={u.id}>
            <span className="ops-table-primary">{u.email}</span>
            <span>{u.role}</span>
            <span className={`ops-status ${u.is_active ? 'ok' : 'watch'}`}>{u.is_active ? 'Aktif' : 'Pasif'}</span>
            <span className="ops-actions">
              <button className="btn btn-outline tight" onClick={() => update(u, { role: u.role === 'admin' ? 'member' : 'admin' })}>
                {u.role === 'admin' ? 'Member yap' : 'Admin yap'}
              </button>
              <button className="btn btn-danger tight" onClick={() => update(u, { is_active: !u.is_active })}>
                {u.is_active ? 'Pasifleştir' : 'Aktifleştir'}
              </button>
            </span>
          </div>
        ))}
      </div>
    </section>
  )
}

function JobsSection() {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try { setJobs(await api.listJobs(20)) } catch { }
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <section className="ops-panel">
      <PanelTitle
        title="İndeks iş kuyruğu"
        action={<button className="btn btn-outline tight" onClick={load} disabled={loading}><IconRefresh /> Yenile</button>}
      />
      <div className="ops-table jobs-admin-table">
        <div className="ops-table-head">
          <span>Dosya</span><span>Durum</span><span>Başlangıç</span><span>Hata</span>
        </div>
        {loading ? (
          <div className="ops-empty compact">Yükleniyor</div>
        ) : jobs.length === 0 ? (
          <div className="ops-empty compact">İş yok</div>
        ) : jobs.map((job) => (
          <div className="ops-table-row" key={job.id}>
            <span className="ops-table-primary">{job.filename}</span>
            <span className={`ops-status ${statusTone(job.status)}`}>{job.status}</span>
            <span>{fmtDate(job.started_at)}</span>
            <span title={job.error_message || ''}>{job.error_message || '-'}</span>
          </div>
        ))}
      </div>
    </section>
  )
}

function EvaluationSection() {
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setRuns(await api.getEvalHistory())
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const activeRun = runs.find((run) => run.status === 'queued' || run.status === 'running')

  useEffect(() => {
    if (!activeRun) return undefined
    const timer = window.setInterval(load, 3000)
    return () => window.clearInterval(timer)
  }, [activeRun?.id, activeRun?.status, load])

  const runEval = async () => {
    setLoading(true); setError('')
    try {
      await api.runEval()
      await load()
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  return (
    <section className="ops-panel">
      <PanelTitle
        title="Eval kayıtları"
        action={(
          <button className="btn btn-primary tight" onClick={runEval} disabled={loading || Boolean(activeRun)}>
            {loading ? 'Yükleniyor' : activeRun?.status === 'queued' ? 'Sırada' : activeRun ? 'Çalışıyor' : 'Eval çalıştır'}
          </button>
        )}
      />
      {error && <div className="ops-alert error">{error}</div>}
      <div className="ops-table eval-admin-table">
        <div className="ops-table-head">
          <span>Etiket</span><span>Durum</span><span>Skor / Soru</span><span>Tarih</span>
        </div>
        {runs.length === 0 ? (
          <div className="ops-empty compact">Eval geçmişi yok</div>
        ) : runs.map((run) => {
          const labels = { queued: 'Sırada', running: 'Çalışıyor', completed: 'Tamamlandı', failed: 'Başarısız' }
          const complete = run.status === 'completed'
          return (
            <div className="ops-table-row" key={run.id}>
              <span className="ops-table-primary">{run.run_label || run.id.slice(0, 8)}</span>
              <span className={`ops-status ${statusTone(run.status)}`} title={run.error || ''}>{labels[run.status] || run.status}</span>
              <span>{complete ? `${Number(run.avg_score || 0).toFixed(3)} / ${run.num_queries}` : '-'}</span>
              <span>{fmtDate(run.created_at)}</span>
            </div>
          )
        })}
      </div>
    </section>
  )
}

function ConfigSection() {
  const configs = [
    { label: 'HyDE', desc: 'Hypothetical Document Embedding', env: 'HYDE_ENABLED', value: 'true' },
    { label: 'Güven Eşiği', desc: 'Rerank confidence threshold', env: 'RERANK_CONFIDENCE_THRESHOLD', value: '-2.0' },
    { label: 'Maks Token', desc: 'LLM max output tokens', env: 'LLM_MAX_TOKENS', value: '512' },
    { label: 'İş Parçacığı', desc: 'LLM CPU threads', env: 'LLM_N_THREADS', value: '8' },
    { label: 'Hız Limiti', desc: 'Per-tenant rate limit', env: 'RATE_LIMIT', value: '60/minute' },
  ]

  return (
    <section className="ops-panel">
      <PanelTitle title="RAG konfigürasyon fişi" meta={`${configs.length} parametre`} />
      <div className="config-ledger">
        {configs.map((c) => (
          <div key={c.env} className="config-row">
            <div>
              <strong>{c.label}</strong>
              <span>{c.desc}</span>
            </div>
            <code title={c.env}>{c.value}</code>
          </div>
        ))}
      </div>
    </section>
  )
}

export default function AdminPanel() {
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshKey, setRefreshKey] = useState(0)

  const load = useCallback(async () => {
    setLoading(true)
    try { setHealth(await api.health()) } catch { }
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load, refreshKey])

  return (
    <div className="ops-page admin-ops">
      <header className="ops-page-header">
        <div>
          <span className="ops-kicker">Yetki, indeks ve sistem kontrolü</span>
          <h2>Operasyon yönetim defteri</h2>
          <p>Tenant, kullanıcı, ingestion, eval ve sağlık kayıtları aynı yönetim yüzeyinde tutulur.</p>
        </div>
        <button
          onClick={() => { load(); setRefreshKey((n) => n + 1) }}
          disabled={loading}
          className="btn btn-outline ops-refresh"
        >
          <IconRefresh /> {loading ? 'Yenileniyor' : 'Yenile'}
        </button>
      </header>

      <section className="ops-grid two">
        <HealthSection health={health} />
        <TenantSection onCreated={() => setRefreshKey((n) => n + 1)} />
      </section>

      <UserSection />

      <section className="ops-grid two">
        <JobsSection />
        <EvaluationSection />
      </section>

      <section className="ops-grid two">
        <DocumentsSection key={refreshKey} />
        <ConfigSection />
      </section>
    </div>
  )
}
