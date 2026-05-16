import React, { useState } from 'react'

const IconFile = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
  </svg>
)

export function CitationPanel({ citations }) {
  const [activeIdx, setActiveIdx] = useState(null)
  if (!citations?.length) return null

  return (
    <div style={{ padding: '12px 14px' }}>
      <div style={{
        fontSize: '10px', fontWeight: 700, color: 'var(--text-3)',
        letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '8px',
      }}>
        Kaynaklar — {citations.length}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {citations.map((cit, i) => (
          <div
            key={i}
            onClick={() => setActiveIdx(activeIdx === i ? null : i)}
            style={{
              cursor: 'pointer',
              border: `1px solid ${activeIdx === i ? 'rgba(99,102,241,0.4)' : 'var(--border)'}`,
              borderRadius: 'var(--radius-sm)',
              overflow: 'hidden',
              background: activeIdx === i ? 'var(--accent-muted)' : 'var(--surface-2)',
              transition: 'all 0.15s',
            }}
          >
            {/* Header row */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: '8px',
              padding: '7px 10px',
            }}>
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: '5px',
                background: 'var(--surface-3)', color: 'var(--accent-hover)',
                borderRadius: 'var(--radius-sm)', padding: '2px 8px',
                fontSize: '11px', fontWeight: 600, maxWidth: 180,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                <IconFile />
                {cit.filename}
              </span>
              <span style={{ fontSize: '11px', color: 'var(--text-3)' }}>
                § {cit.chunk_index}
              </span>
              <span style={{
                marginLeft: 'auto', fontSize: '11px',
                color: activeIdx === i ? 'var(--accent)' : 'var(--text-3)',
              }}>
                {activeIdx === i ? '↑' : '↓'}
              </span>
            </div>

            {/* Expanded text */}
            {activeIdx === i && (
              <div className="fade-in" style={{
                padding: '8px 10px 10px',
                borderTop: '1px solid var(--border)',
                fontSize: '12.5px', color: 'var(--text-2)',
                lineHeight: 1.65, fontStyle: 'italic',
              }}>
                "{cit.text_preview}{cit.text_preview?.length >= 120 ? '…' : ''}"
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
