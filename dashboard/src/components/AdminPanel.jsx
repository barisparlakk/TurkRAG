import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client.js'

/* ── Icons ─────────────────────────────────────────────────────────────────── */
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

/* ── Section title ──────────────────────────────────────────────────────────── */
function SectionTitle({ children }) {
  return (
    <div className="section-label">
      {children}
    </div>
  )
}

/* ── Status pill ────────────────────────────────────────────────────────────── */
function StatusPill({ ok, label }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '6px',
      background: ok ? 'var(--success-muted)' : 'var(--error-muted)',
      border: `1px solid ${ok ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)'}`,
      color: ok ? 'var(--success)' : 'var(--error)',
      borderRadius: 20, padding: '4px 10px', fontSize: '12px', fontWeight: 600,
    }}>
      {ok ? <IconCheck /> : <IconX />}
      {label}
    </div>
  )
}

/* ── Health section ─────────────────────────────────────────────────────────── */
function HealthSection({ health }) {
  if (!health) return null
  return (
    <div style={{
      background: 'var(--surface-1)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)', padding: '20px 22px',
    }}>
      <SectionTitle>Sistem Durumu</SectionTitle>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
        <StatusPill ok={health.status === 'ok'} label="API" />
        <StatusPill ok={health.qdrant === 'ok'} label="Qdrant" />
        <StatusPill ok={health.postgres === 'ok'} label="PostgreSQL" />
        <StatusPill ok={health.llm_available} label="LLM" />
      </div>
      {health.version && (
        <div style={{ fontSize: '11px', color: 'var(--text-3)', marginTop: '10px' }}>
          v{health.version}
        </div>
      )}
    </div>
  )
}

/* ── Tenant create section ──────────────────────────────────────────────────── */
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

  // Auto-generate slug from name
  const handleNameChange = (val) => {
    setName(val)
    setSlug(val.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, ''))
  }

  return (
    <div style={{
      background: 'var(--surface-1)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)', padding: '20px 22px',
    }}>
      <SectionTitle>Kiracı Yönetimi</SectionTitle>

      {tenants.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '16px' }}>
          {tenants.map((t) => (
            <div key={t.id} style={{
              background: 'var(--surface-2)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)', padding: '6px 12px',
              fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '2px',
            }}>
              <span style={{ fontWeight: 600, color: 'var(--text-1)' }}>{t.name}</span>
              <span style={{ color: 'var(--text-3)', fontFamily: 'monospace' }}>{t.slug}</span>
            </div>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <input
            type="text"
            placeholder="Kiracı adı"
            value={name}
            onChange={(e) => handleNameChange(e.target.value)}
            className="input-field"
            style={{ flex: '1 1 160px' }}
            required
          />
          <input
            type="text"
            placeholder="slug (otomatik)"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            className="input-field"
            style={{ flex: '1 1 140px', fontFamily: 'monospace', fontSize: '13px' }}
            required
          />
          <button
            type="submit"
            disabled={loading || !name.trim() || !slug.trim()}
            className="btn btn-primary"
            style={{ padding: '8px 16px', fontSize: '13px', flexShrink: 0 }}
          >
            {loading ? '...' : 'Oluştur'}
          </button>
        </div>

        {error && (
          <div style={{
            background: 'var(--error-muted)', border: '1px solid rgba(239,68,68,0.2)',
            color: 'var(--error)', fontSize: '12px',
            borderRadius: 'var(--radius-md)', padding: '8px 12px',
          }}>
            {error}
          </div>
        )}
        {success && (
          <div style={{
            background: 'var(--success-muted)', border: '1px solid rgba(16,185,129,0.2)',
            color: 'var(--success)', fontSize: '12px',
            borderRadius: 'var(--radius-md)', padding: '8px 12px',
          }}>
            {success}
          </div>
        )}
      </form>
    </div>
  )
}

/* ── Documents section ──────────────────────────────────────────────────────── */
function DocumentsSection() {
  const [docs, setDocs] = useState([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try { setDocs(await api.listDocuments()) } catch { }
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  const statusBadge = (status) => {
    if (status === 'ready') return { label: 'Hazır', color: 'var(--success)', bg: 'var(--success-muted)' }
    if (status === 'error') return { label: 'Hata', color: 'var(--error)', bg: 'var(--error-muted)' }
    return { label: 'İşleniyor', color: 'var(--warning)', bg: 'var(--warning-muted)' }
  }

  return (
    <div style={{
      background: 'var(--surface-1)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)', overflow: 'hidden',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '16px 20px', borderBottom: '1px solid var(--border)',
        background: 'var(--surface-2)',
      }}>
        <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-3)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
          Belgeler ({docs.length})
        </div>
        <button onClick={load} disabled={loading} className="btn" style={{
          fontSize: '11px', padding: '4px 10px', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-md)', color: 'var(--text-2)',
          display: 'flex', alignItems: 'center', gap: '5px',
          opacity: loading ? 0.5 : 1,
        }}>
          <IconRefresh />
        </button>
      </div>

      {loading ? (
        <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-3)', fontSize: '13px' }}>
          Yükleniyor
        </div>
      ) : docs.length === 0 ? (
        <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-3)', fontSize: '13px' }}>
          Belge yok
        </div>
      ) : (
        <>
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 80px 60px 100px',
            padding: '8px 20px', borderBottom: '1px solid var(--border)',
            fontSize: '11px', fontWeight: 700, color: 'var(--text-3)',
            letterSpacing: '0.06em', textTransform: 'uppercase',
          }}>
            <div>Dosya</div>
            <div style={{ textAlign: 'center' }}>Durum</div>
            <div style={{ textAlign: 'right' }}>Parça</div>
            <div style={{ textAlign: 'right' }}>Tarih</div>
          </div>

          {docs.map((doc, i) => {
            const badge = statusBadge(doc.status)
            return (
              <div key={doc.id} style={{
                display: 'grid', gridTemplateColumns: '1fr 80px 60px 100px',
                padding: '10px 20px', alignItems: 'center',
                borderBottom: i < docs.length - 1 ? '1px solid var(--border)' : 'none',
                fontSize: '13px',
              }}>
                <div style={{
                  color: 'var(--text-1)', overflow: 'hidden',
                  textOverflow: 'ellipsis', whiteSpace: 'nowrap', paddingRight: 12,
                }}>
                  {doc.filename}
                </div>
                <div style={{ display: 'flex', justifyContent: 'center' }}>
                  <span style={{
                    fontSize: '11px', fontWeight: 600,
                    background: badge.bg, color: badge.color,
                    borderRadius: 20, padding: '2px 8px',
                  }}>
                    {badge.label}
                  </span>
                </div>
                <div style={{ textAlign: 'right', color: 'var(--text-2)' }}>
                  {doc.chunk_count ?? '—'}
                </div>
                <div style={{ textAlign: 'right', color: 'var(--text-3)', fontSize: '11px' }}>
                  {new Date(doc.created_at).toLocaleDateString('tr-TR', { month: 'short', day: 'numeric' })}
                </div>
              </div>
            )
          })}
        </>
      )}
    </div>
  )
}

/* ── RAG Config section ─────────────────────────────────────────────────────── */
function ConfigSection() {
  const configs = [
    { label: 'HyDE', desc: 'Hypothetical Document Embedding', env: 'HYDE_ENABLED', default: 'true' },
    { label: 'Güven Eşiği', desc: 'Rerank confidence threshold', env: 'RERANK_CONFIDENCE_THRESHOLD', default: '-2.0' },
    { label: 'Maks Token', desc: 'LLM max output tokens', env: 'LLM_MAX_TOKENS', default: '512' },
    { label: 'İş Parçacığı', desc: 'LLM CPU threads', env: 'LLM_N_THREADS', default: '8' },
    { label: 'Hız Limiti', desc: 'Per-tenant rate limit', env: 'RATE_LIMIT', default: '60/minute' },
  ]

  return (
    <div style={{
      background: 'var(--surface-1)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)', padding: '20px 22px',
    }}>
      <SectionTitle>RAG Konfigürasyonu</SectionTitle>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
        {configs.map((c, i) => (
          <div key={c.env} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '10px 0',
            borderBottom: i < configs.length - 1 ? '1px solid var(--border)' : 'none',
          }}>
            <div>
              <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-1)' }}>{c.label}</div>
              <div style={{ fontSize: '11px', color: 'var(--text-3)', marginTop: 2 }}>{c.desc}</div>
            </div>
            <div style={{
              fontFamily: 'monospace', fontSize: '12px',
              background: 'var(--surface-2)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)', padding: '3px 8px', color: 'var(--accent-hover)',
            }}>
              {c.default}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ── Main ───────────────────────────────────────────────────────────────────── */
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div className="view-header">
        <h2>Yönetim</h2>
        <button
          onClick={() => { load(); setRefreshKey((n) => n + 1) }}
          disabled={loading}
          className="btn btn-outline"
          style={{ opacity: loading ? 0.5 : 1 }}
        >
          <IconRefresh /> {loading ? '...' : 'Yenile'}
        </button>
      </div>

      <HealthSection health={health} />
      <TenantSection onCreated={() => setRefreshKey((n) => n + 1)} />
      <DocumentsSection key={refreshKey} />
      <ConfigSection />
    </div>
  )
}
