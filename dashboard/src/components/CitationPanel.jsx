import React, { useState } from 'react'

export function CitationPanel({ citations }) {
  const [activeIdx, setActiveIdx] = useState(null)

  if (!citations || citations.length === 0) return null

  return (
    <div style={{
      borderTop: '1px solid #e0e0e0',
      padding: '10px 12px',
      background: '#fafafa',
    }}>
      <div style={{ fontSize: '12px', color: '#666', marginBottom: '6px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        Kaynaklar ({citations.length})
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {citations.map((cit, i) => (
          <div
            key={i}
            onClick={() => setActiveIdx(activeIdx === i ? null : i)}
            style={{
              cursor: 'pointer',
              border: `1px solid ${activeIdx === i ? '#1a73e8' : '#e0e0e0'}`,
              borderRadius: '6px',
              padding: '8px 10px',
              background: activeIdx === i ? '#e8f4fd' : '#fff',
              transition: 'all 0.15s',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: activeIdx === i ? '6px' : 0 }}>
              <span style={{
                background: '#1a73e8',
                color: '#fff',
                borderRadius: '4px',
                padding: '1px 7px',
                fontSize: '11px',
                fontWeight: 700,
                whiteSpace: 'nowrap',
              }}>
                {cit.filename}
              </span>
              <span style={{ fontSize: '12px', color: '#888' }}>Bölüm {cit.chunk_index}</span>
              <span style={{ marginLeft: 'auto', fontSize: '12px', color: '#1a73e8' }}>
                {activeIdx === i ? '▲' : '▼'}
              </span>
            </div>
            {activeIdx === i && (
              <div style={{ fontSize: '13px', color: '#444', lineHeight: 1.5, borderTop: '1px solid #dde8fb', paddingTop: '6px' }}>
                {cit.text_preview}…
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
