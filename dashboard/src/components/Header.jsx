import React, { useState } from 'react'

const IconSun = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="5"/>
    <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
    <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
  </svg>
)
const IconMoon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
  </svg>
)
const IconChevron = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="6 9 12 15 18 9"/>
  </svg>
)
const IconLogout = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
    <polyline points="16 17 21 12 16 7"/>
    <line x1="21" y1="12" x2="9" y2="12"/>
  </svg>
)

export function Header({ tenant, tenants = [], onTenantSwitch, onLogout, theme, onThemeToggle }) {
  const [userOpen, setUserOpen] = useState(false)
  const [tenantOpen, setTenantOpen] = useState(false)

  return (
    <header style={{
      height: 'var(--header-h)', flexShrink: 0,
      borderBottom: '1px solid var(--border)',
      background: 'var(--glass-bg)',
      backdropFilter: 'var(--glass-blur)',
      WebkitBackdropFilter: 'var(--glass-blur)',
      display: 'flex', alignItems: 'center',
      padding: '0 16px', gap: '0',
      position: 'sticky', top: 0, zIndex: 100,
    }}>
      {/* Logo */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px',
        width: 'var(--sidebar-w)', flexShrink: 0,
        paddingRight: '16px',
      }}>
        <div style={{ width: 30, height: 30, flexShrink: 0 }}>
          <img src="/logo-light.png" className="logo-light" style={{ width: 30, height: 30, objectFit: 'contain' }} alt="" />
          <img src="/logo-dark.png"  className="logo-dark"  style={{ width: 30, height: 30, objectFit: 'contain' }} alt="" />
        </div>
        <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-1)', letterSpacing: '-0.01em' }}>
          TurkRAG
        </span>
      </div>

      {/* Tenant selector */}
      <div style={{ position: 'relative' }}>
        <button
          onClick={() => setTenantOpen((v) => !v)}
          className="btn"
          style={{
            border: '1px solid var(--border)', borderRadius: 'var(--radius-md)',
            padding: '5px 10px', fontSize: '13px', color: 'var(--text-1)',
            gap: '6px',
          }}
        >
          <span style={{
            width: 6, height: 6, borderRadius: '50%',
            background: 'var(--success)', flexShrink: 0,
          }} />
          {tenant?.name || tenant?.slug || 'Kiracı seç'}
          <IconChevron />
        </button>

        {tenantOpen && tenants.length > 1 && (
          <div className="fade-in" style={{
            position: 'absolute', top: '100%', left: 0, marginTop: 4,
            background: 'var(--bg)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-lg)',
            boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
            minWidth: 180, zIndex: 200, overflow: 'hidden',
          }}>
            {tenants.map((t) => (
              <button
                key={t.id}
                onClick={() => { onTenantSwitch?.(t); setTenantOpen(false) }}
                className="btn"
                style={{
                  width: '100%', justifyContent: 'flex-start',
                  padding: '9px 14px', borderRadius: 0,
                  fontWeight: t.id === tenant?.id ? 600 : 400,
                  color: t.id === tenant?.id ? 'var(--accent)' : 'var(--text-1)',
                }}
              >
                {t.name}
              </button>
            ))}
          </div>
        )}
      </div>

      <div style={{ flex: 1 }} />

      {/* Theme toggle */}
      <button
        onClick={onThemeToggle}
        className="btn btn-ghost"
        style={{ width: 36, height: 36, padding: 0, borderRadius: 'var(--radius-md)' }}
        title={theme === 'dark' ? 'Açık mod' : 'Koyu mod'}
      >
        {theme === 'dark' ? <IconSun /> : <IconMoon />}
      </button>

      {/* User menu */}
      <div style={{ position: 'relative', marginLeft: 4 }}>
        <button
          onClick={() => setUserOpen((v) => !v)}
          style={{
            width: 32, height: 32, borderRadius: '50%',
            background: 'var(--accent-muted)',
            border: '1px solid var(--border)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer', color: 'var(--accent)', fontSize: '12px', fontWeight: 700,
          }}
        >
          {(tenant?.slug?.[0] || 'U').toUpperCase()}
        </button>

        {userOpen && (
          <div className="fade-in" onClick={() => setUserOpen(false)} style={{
            position: 'absolute', top: '100%', right: 0, marginTop: 4,
            background: 'var(--bg)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-lg)',
            boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
            minWidth: 160, zIndex: 200, overflow: 'hidden',
          }}>
            <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)' }}>
              <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-1)' }}>{tenant?.name}</div>
              <div style={{ fontSize: '11px', color: 'var(--text-3)', marginTop: 2, fontFamily: 'monospace' }}>{tenant?.slug}</div>
            </div>
            <button
              onClick={onLogout}
              className="btn btn-ghost"
              style={{
                width: '100%', justifyContent: 'flex-start',
                padding: '9px 14px', borderRadius: 0, color: 'var(--error)',
                gap: '8px',
              }}
            >
              <IconLogout /> Çıkış Yap
            </button>
          </div>
        )}
      </div>

      {/* Click-outside overlay */}
      {(userOpen || tenantOpen) && (
        <div
          style={{ position: 'fixed', inset: 0, zIndex: 150 }}
          onClick={() => { setUserOpen(false); setTenantOpen(false) }}
        />
      )}
    </header>
  )
}
