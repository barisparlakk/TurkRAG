import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client.js'

function fmtTime(ms) {
  if (!ms) return '-'
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} sn` : `${ms} ms`
}

function fmtDate(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString('tr-TR', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function OpsMetric({ code, label, value, detail, tone = 'neutral' }) {
  return (
    <div className={`ops-metric tone-${tone}`}>
      <code>{code}</code>
      <span>{label}</span>
      <strong>{value ?? '-'}</strong>
      <small>{detail}</small>
    </div>
  )
}

function QueryList({ rows }) {
  if (!rows?.length) {
    return <div className="ops-empty compact">Henüz tekrar eden sorgu kaydı yok</div>
  }

  return (
    <div className="ops-ledger">
      {rows.map((q, index) => (
        <div className="ops-ledger-row" key={`${q.query}-${index}`}>
          <code>S{String(index + 1).padStart(2, '0')}</code>
          <span>{q.query}</span>
          <strong>{q.count}x</strong>
        </div>
      ))}
    </div>
  )
}

function SourceList({ rows }) {
  if (!rows?.length) {
    return <div className="ops-empty compact">Henüz alıntılanan kaynak yok</div>
  }

  return (
    <div className="ops-ledger source-ledger">
      {rows.map((doc, index) => (
        <div className="ops-ledger-row" key={`${doc.filename}-${index}`}>
          <code>K{String(index + 1).padStart(2, '0')}</code>
          <span>{doc.filename}</span>
          <strong>{doc.citations} atıf</strong>
        </div>
      ))}
    </div>
  )
}

function RecentQueries({ rows }) {
  if (!rows?.length) {
    return <div className="ops-empty">Henüz sorgu kaydı yok</div>
  }

  return (
    <div className="ops-table analytics-table">
      <div className="ops-table-head">
        <span>Sorgu</span>
        <span>Atıf</span>
        <span>Süre</span>
        <span>Zaman</span>
      </div>
      {rows.map((row) => (
        <div className="ops-table-row" key={row.id}>
          <span className="ops-table-primary">{row.query}</span>
          <span>{row.num_citations ?? 0}</span>
          <span>{fmtTime(row.query_time_ms)}</span>
          <span>{fmtDate(row.created_at)}</span>
        </div>
      ))}
    </div>
  )
}

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

  return (
    <div className="ops-page analytics-ops">
      <header className="ops-page-header">
        <div>
          <span className="ops-kicker">Kalite ve kullanım kayıtları</span>
          <h2>Yanıt hattı ölçüm masası</h2>
          <p>Tenant içindeki sorgu hacmi, kaynak kullanımı ve yanıt süreleri tek defterde izlenir.</p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="btn btn-outline ops-refresh"
        >
          {loading ? 'Yenileniyor' : 'Yenile'}
        </button>
      </header>

      {error && <div className="ops-alert error">Hata: {error}</div>}

      <section className="ops-metric-strip" aria-label="Analitik özeti">
        <OpsMetric
          code="Q"
          label="Toplam sorgu"
          value={stats?.total_queries ?? '-'}
          detail="tüm zamanlar"
        />
        <OpsMetric
          code="24"
          label="Bugünkü hacim"
          value={stats?.queries_today ?? '-'}
          detail="son 24 saat"
          tone="good"
        />
        <OpsMetric
          code="RT"
          label="Ortalama süre"
          value={stats ? fmtTime(stats.avg_query_time_ms) : '-'}
          detail="yanıt üretimi"
          tone="watch"
        />
      </section>

      <section className="ops-grid two">
        <article className="ops-panel">
          <div className="ops-panel-head">
            <span>Sorgu yoğunluğu</span>
            <strong>{stats?.top_queries?.length || 0} kayıt</strong>
          </div>
          <QueryList rows={stats?.top_queries} />
        </article>

        <article className="ops-panel">
          <div className="ops-panel-head">
            <span>Kaynak etkisi</span>
            <strong>{stats?.top_documents?.length || 0} belge</strong>
          </div>
          <SourceList rows={stats?.top_documents} />
        </article>
      </section>

      <section className="ops-panel">
        <div className="ops-panel-head">
          <span>Son sorgu hareketleri</span>
          <strong>{recent.length} satır</strong>
        </div>
        <RecentQueries rows={recent} />
      </section>

      {lastRefresh && (
        <div className="ops-timestamp">
          Son güncelleme: {lastRefresh.toLocaleTimeString('tr-TR')}
        </div>
      )}
    </div>
  )
}
