import React from 'react'

export function TenantBadge({ tenantSlug }) {
  if (!tenantSlug) return null

  return (
    <div style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '6px',
      background: '#e8f4fd',
      border: '1px solid #b8d9f5',
      borderRadius: '20px',
      padding: '4px 12px',
      fontSize: '13px',
      color: '#1a73e8',
      fontWeight: 500,
    }}>
      <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#1a73e8', display: 'inline-block' }} />
      {tenantSlug}
    </div>
  )
}
