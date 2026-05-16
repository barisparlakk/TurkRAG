import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client.js'

/* ── Stat card ─────────────────────────────────────────────────────────────── */
function StatCard({ label, value, sub, color = 'var(--accent)' }) {
  return (
    <div style={{
      background: 'var(--surface-1)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)',
      padding: '20px 22px',
      flex: '1 1 160px',
    }}>
      <div style={{ fontSize: '12px', color: 'var(--text-3)', fontWeight: 600,
                    letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '10px' }}>
        {label}
      </div>
      <div style={{ fontSize: '32px', fontWeight: 700, color, lineHeight: 1 }}>
        {value ?? '—'}
      </div>
      {sub && (
        <div style={{ fontSize: '12px', color: 'var(--text-3)', marginTop: '6px' }}>{sub}</div>
      )}
    </div>
  )
}

/* ── Section header ────────────────────────────────────────────────────────── */
function SectionTitle({ children }) {
  return (
    <div style={{
      fontSize: '11px', fontWeight: 700, color: 'var(--text-3)',
      letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '10px',
    }}>
      {children}
    </div>
  )
}

/* ── Main dashboard ────────────────────────────────────────────────────────── */
export function AnalyticsDashboard() {
  const [stats, setStats] = useState(null)
  const [recent, setRecent] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lastRefresh, setLastRefresh] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [s, r] = await Promise.all([
        api.getStats(),
        api.getRecentQueries(15),
      ])
      setStats(s)
      setRecent(r)
      setLastRefresh(new Date())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const fmtTime = (ms) => {
    if (!ms) return '—'
    return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`
  }

  const fmtDate = (iso) => {
    if (!iso) return '—'
    const d = new Date(iso)
    return d.toLocaleString('tr-TR', { month: 'short', day: 'numeric',
                                        hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-1)', marginBottom: '4px' }}>
            Analitik
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-2)' }}>
            Sorgu istatistikleri ve kullanım özeti
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="btn"
          style={{
            fontSize: '12px', padding: '6px 14px',
            border: '1px solid var(--border)', borderRadius: 'var(--radius-md)',
            color: 'var(--text-2)', opacity: loading ? 0.5 : 1,
          }}
        >
          {loading ? 'Yükleniyor…' : '↻ Yenile'}
        </button>
      </div>

      {error && (
        <div style={{
          background: 'var(--error-muted)', border: '1px solid rgba(239,68,68,0.2)',
          color: 'var(--error)', fontSize: '13px',
          borderRadius: 'var(--radius-md)', padding: '10px 14px',
        }}>
          Veriler yüklenirken hata: {error}
        </div>
      )}

      {/* Stat cards */}
      <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap' }}>
        <StatCard
          label="Toplam Sorgu"
          value={stats?.total_queries ?? '—'}
          sub="Tüm zamanlar"
        />
        <StatCard
          label="Bugün"
          value={stats?.queries_today ?? '—'}
          sub="Son 24 saat"
          color="#10b981"
        />
        <StatCard
          label="Ort. Yanıt Süresi"
          value={stats ? fmtTime(stats.avg_query_time_ms) : '—'}
          sub="Tüm sorgular"
          color="#f59e0b"
        />
      </div>

      {/* Top queries + top docs side by side */}
      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
        {/* Top questions */}
        <div style={{
          flex: '1 1 280px',
          background: 'var(--surface-1)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)', padding: '18px 20px',
        }}>
          <SectionTitle>En Çok Sorulan</SectionTitle>
          {!stats?.top_queries?.length ? (
            <div style={{ fontSize: '13px', color: 'var(--text-3)' }}>Henüz veri yok</div>
          ) : (
            <ol style={{ margin: 0, padding: '0 0 0 18px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {stats.top_queries.map((q, i) => (
                <li key={i} style={{ fontSize: '13px', color: 'var(--text-1)', lineHeight: 1.5 }}>
                  <span style={{ color: 'var(--text-3)', marginRight: 4 }}>×{q.count}</span>
                  {q.query.length > 80 ? q.query.slice(0, 80) + '…' : q.query}
                </li>
              ))}
            </ol>
          )}
        </div>

        {/* Top documents */}
        <div style={{
          flex: '1 1 280px',
          background: 'var(--surface-1)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)', padding: '18px 20px',
        }}>
          <SectionTitle>En Çok Alıntılanan Belgeler</SectionTitle>
          {!stats?.top_documents?.length ? (
            <div style={{ fontSize: '13px', color: 'var(--text-3)' }}>Henüz veri yok</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {stats.top_documents.map((d, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{
                    fontSize: '11px', fontWeight: 700,
                    background: 'var(--accent-muted)', color: 'var(--accent)',
                    borderRadius: 4, padding: '2px 6px', flexShrink: 0,
                  }}>
                    {d.citations}×
                  </div>
                  <span style={{
                    fontSize: '13px', color: 'var(--text-1)',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>
                    {d.filename}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Recent queries table */}
      <div>
        <SectionTitle>Son Sorgular</SectionTitle>
        {recent.length === 0 ? (
          <div style={{
            background: 'var(--surface-1)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)', padding: '28px',
            textAlign: 'center', color: 'var(--text-3)', fontSize: '13px',
          }}>
            Henüz sorgu kaydı yok
          </div>
        ) : (
          <div style={{
            background: 'var(--surface-1)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-lg)', overflow: 'hidden',
          }}>
            {/* Table header */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 70px 70px 110px',
              padding: '10px 16px',
              borderBottom: '1px solid var(--border)',
              fontSize: '11px', fontWeight: 700,
              color: 'var(--text-3)', letterSpacing: '0.06em', textTransform: 'uppercase',
              background: 'var(--surface-2)',
            }}>
              <div>Sorgu</div>
              <div style={{ textAlign: 'right' }}>Alıntı</div>
              <div style={{ textAlign: 'right' }}>Süre</div>
              <div style={{ textAlign: 'right' }}>Tarih</div>
            </div>
            {/* Rows */}
            {recent.map((row, i) => (
              <div
                key={row.id}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 70px 70px 110px',
                  padding: '10px 16px',
                  borderBottom: i < recent.length - 1 ? '1px solid var(--border)' : 'none',
                  fontSize: '13px',
                  alignItems: 'center',
                }}
              >
                <div style={{
                  color: 'var(--text-1)',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  paddingRight: '12px',
                }}>
                  {row.query}
                </div>
                <div style={{ textAlign: 'right', color: 'var(--text-2)' }}>
                  {row.num_citations ?? 0}
                </div>
                <div style={{ textAlign: 'right', color: 'var(--text-2)' }}>
                  {fmtTime(row.query_time_ms)}
                </div>
                <div style={{ textAlign: 'right', color: 'var(--text-3)', fontSize: '12px' }}>
                  {fmtDate(row.created_at)}
                </div>
              </div>
            ))}
          </div>
        )}
        {lastRefresh && (
          <div style={{ fontSize: '11px', color: 'var(--text-3)', marginTop: '8px', textAlign: 'right' }}>
            Son güncelleme: {lastRefresh.toLocaleTimeString('tr-TR')}
          </div>
        )}
      </div>
    </div>
  )
}
