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

export function Header({ tenant, tenants = [], role, onTenantSwitch, onLogout, theme, onThemeToggle }) {
  const [userOpen, setUserOpen] = useState(false)
  const [tenantOpen, setTenantOpen] = useState(false)

  return (
    <header className="app-header">
      <div className="app-brand">
        <div className="app-brand-logo">
          <img src="/logo-light.png" className="logo-light" alt="" />
          <img src="/logo-dark.png" className="logo-dark" alt="" />
        </div>
        <span>TurkRAG</span>
      </div>

      <div style={{ position: 'relative' }}>
        <button
          onClick={() => setTenantOpen((v) => !v)}
          className="tenant-switch"
        >
          <span className="status-dot" />
          <span>{tenant?.name || tenant?.slug || 'Kiracı'}</span>
          <IconChevron />
        </button>

        {tenantOpen && tenants.length > 1 && (
          <div className="header-menu fade-in">
            {tenants.map((t) => (
              <button
                key={t.id}
                onClick={() => { onTenantSwitch?.(t); setTenantOpen(false) }}
                className={`menu-row ${t.id === tenant?.id ? 'active' : ''}`}
              >
                {t.name}
              </button>
            ))}
          </div>
        )}
      </div>

      <div style={{ flex: 1 }} />

      <span className="role-chip">{role === 'admin' ? 'Admin' : 'Member'}</span>

      <button
        onClick={onThemeToggle}
        className="icon-btn"
        title={theme === 'dark' ? 'Açık mod' : 'Koyu mod'}
      >
        {theme === 'dark' ? <IconSun /> : <IconMoon />}
      </button>

      <div style={{ position: 'relative', marginLeft: 4 }}>
        <button
          onClick={() => setUserOpen((v) => !v)}
          className="avatar-btn"
        >
          {(tenant?.slug?.[0] || 'U').toUpperCase()}
        </button>

        {userOpen && (
          <div className="header-menu user-menu fade-in" onClick={() => setUserOpen(false)}>
            <div className="menu-meta">
              <strong>{tenant?.name}</strong>
              <span>{tenant?.slug}</span>
            </div>
            <button
              onClick={onLogout}
              className="menu-row danger"
            >
              <IconLogout /> Çıkış
            </button>
          </div>
        )}
      </div>

      {(userOpen || tenantOpen) && (
        <div
          style={{ position: 'fixed', inset: 0, zIndex: 150 }}
          onClick={() => { setUserOpen(false); setTenantOpen(false) }}
        />
      )}
    </header>
  )
}
