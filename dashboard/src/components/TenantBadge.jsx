import React from 'react'

export function TenantBadge({ tenantSlug }) {
  if (!tenantSlug) return null
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: '6px',
      background: 'var(--accent-muted)',
      border: '1px solid rgba(99,102,241,0.25)',
      borderRadius: 20, padding: '4px 12px',
      fontSize: '12px', color: 'var(--accent-hover)', fontWeight: 600,
    }}>
      <span style={{
        width: 6, height: 6, borderRadius: '50%',
        background: 'var(--success)',
        boxShadow: '0 0 6px var(--success)',
      }} />
      {tenantSlug}
    </div>
  )
}
