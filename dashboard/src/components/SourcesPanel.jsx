import React from 'react'

/* ── File type icon ─────────────────────────────────────── */
function FileIcon({ filename }) {
  const ext = filename?.split('.').pop()?.toLowerCase() || ''
  const colors = {
    pdf:  '#ef4444', docx: '#3b82f6', txt: '#10b981',
    xlsx: '#16a34a', xls: '#16a34a',  csv: '#f59e0b',
  }
  const color = colors[ext] || 'var(--text-3)'
  return (
    <div style={{
      width: 28, height: 28, borderRadius: 6, flexShrink: 0,
      background: `${color}18`, border: `1px solid ${color}30`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
      </svg>
    </div>
  )
}

/* ── Relevance pill ─────────────────────────────────────── */
function RelevancePill({ score }) {
  if (score == null) return null
  const pct = Math.round(score * 100)
  let color, bg
  if (pct >= 85) { color = 'var(--success)'; bg = 'var(--success-muted)' }
  else if (pct >= 60) { color = 'var(--warning)'; bg = 'var(--warning-muted)' }
  else { color = 'var(--error)'; bg = 'var(--error-muted)' }

  return (
    <span style={{
      fontSize: '11px', fontWeight: 600,
      background: bg, color,
      borderRadius: 20, padding: '1px 7px', flexShrink: 0,
    }}>
      {pct}%
    </span>
  )
}

/* ── Single source card ─────────────────────────────────── */
function SourceCard({ citation, index }) {
  const [expanded, setExpanded] = React.useState(false)

  return (
    <div
      className={`source-record ${expanded ? 'expanded' : ''}`}
      onClick={() => setExpanded((v) => !v)}
    >
      {/* Top row */}
      <div className="source-record-head">
        <span className="source-index">K{String(index + 1).padStart(2, '0')}</span>
        <FileIcon filename={citation.filename} />
        <div className="source-record-meta">
          <div>
            {citation.filename}
          </div>
          <small>Parça {citation.chunk_index}</small>
        </div>
        <RelevancePill score={citation.score} />
      </div>

      {/* Preview snippet */}
      {citation.text_preview && (
        <div className="source-preview" style={{ WebkitLineClamp: expanded ? 999 : 3 }}>
          "{citation.text_preview}{!expanded && citation.text_preview.length >= 119 ? '…' : ''}"
        </div>
      )}
    </div>
  )
}

/* ── Attribution section ────────────────────────────────── */
function AttributionSection({ sentences }) {
  if (!sentences?.length) return null

  return (
    <div style={{ marginBottom: '12px' }}>
      <div className="section-label">Atıf</div>
      <div style={{
        background: 'var(--surface-1)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)',
        padding: '10px 12px',
        fontSize: '12.5px',
        lineHeight: 1.7,
        color: 'var(--text-1)',
      }}>
        {sentences.map((s, i) => {
          const isLow = s.sources?.[0]?.low_confidence
          const hasSource = s.sources?.length > 0
          let style = {}
          let title = ''
          if (hasSource && !isLow) {
            style = {
              borderBottom: '2px solid #22c55e',
              cursor: 'help',
            }
            title = `Kaynak: ${s.sources[0].filename} (${Math.round(s.sources[0].score * 100)}%)`
          } else if (hasSource && isLow) {
            style = {
              borderBottom: '2px solid #f59e0b',
              cursor: 'help',
            }
            title = `Düşük güven: ${s.sources[0].filename}`
          }
          return (
            <span key={i} style={style} title={title}>
              {s.text}{' '}
            </span>
          )
        })}
      </div>
      <div style={{ display: 'flex', gap: '12px', marginTop: '6px', fontSize: '11px', color: 'var(--text-3)' }}>
        <span><span style={{ borderBottom: '2px solid #22c55e', paddingBottom: 1 }}>--</span> Net</span>
        <span><span style={{ borderBottom: '2px solid #f59e0b', paddingBottom: 1 }}>--</span> Zayıf</span>
      </div>
    </div>
  )
}

/* ── Panel ──────────────────────────────────────────────── */
export function SourcesPanel({ citations, attribution }) {
  return (
    <aside className="sources-panel">
      <div className="sources-header">
        <span>Kanıt Paneli</span>
        {citations?.length > 0 && (
          <span className="badge badge-accent">{citations.length}</span>
        )}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '12px' }}>
        <AttributionSection sentences={attribution} />
        {!citations?.length ? (
          <div className="sources-empty">
            <div className="sources-empty-icon">
              <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <path d="M8 13h8M8 17h5"/>
              </svg>
            </div>
            <strong>Kaynak bekleniyor</strong>
            <span>Yanıt geldikten sonra kullanılan belge parçaları burada görünür.</span>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {citations.map((cit, i) => (
              <SourceCard key={i} citation={cit} index={i} />
            ))}
          </div>
        )}
      </div>
    </aside>
  )
}
