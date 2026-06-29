import React, { useState } from 'react'

const IconSearch = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.3-4.3" />
  </svg>
)
const IconSun = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
  </svg>
)
const IconMoon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 12.8A8.5 8.5 0 1 1 11.2 3 6.6 6.6 0 0 0 21 12.8z" />
  </svg>
)
const IconBell = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M13.7 21a2 2 0 0 1-3.4 0" />
  </svg>
)
const IconRefresh = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 12a9 9 0 0 1-15.5 6.2" /><path d="M3 12A9 9 0 0 1 18.5 5.8" /><path d="M3 5v6h6M21 19v-6h-6" />
  </svg>
)
const IconLogout = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="M16 17l5-5-5-5" /><path d="M21 12H9" />
  </svg>
)

export function Header({
  tenant,
  tenants = [],
  role,
  onTenantSwitch,
  onLogout,
  theme,
  onThemeToggle,
  onSearch,
  onRefresh,
}) {
  const [userOpen, setUserOpen] = useState(false)
  const [tenantOpen, setTenantOpen] = useState(false)
  const roleLabel = role === 'platform_admin' ? 'Platform' : role === 'admin' ? 'Admin' : 'Member'

  return (
    <header className="app-topbar">
      <div className="global-search">
        <IconSearch />
        <input
          type="search"
          placeholder="Search anything..."
          onChange={(event) => onSearch?.(event.target.value)}
          aria-label="Search dashboard"
        />
        <kbd>⌘ K</kbd>
      </div>

      <div className="topbar-actions">
        <button className="topbar-icon" type="button" onClick={onRefresh} title="Refresh data">
          <IconRefresh />
        </button>
        <button className="topbar-icon" type="button" onClick={onThemeToggle} title={theme === 'dark' ? 'Light mode' : 'Dark mode'}>
          {theme === 'dark' ? <IconSun /> : <IconMoon />}
        </button>
        <button className="topbar-icon has-dot" type="button" title="Notifications">
          <IconBell />
        </button>

        <div className="tenant-control">
          <button className="tenant-chip" type="button" onClick={() => setTenantOpen((value) => !value)}>
            <span className="status-dot" />
            <span>{tenant?.name || tenant?.slug || 'Tenant'}</span>
          </button>
          {tenantOpen && tenants.length > 1 && (
            <div className="topbar-menu">
              {tenants.map((item) => (
                <button
                  key={item.id}
                  className={item.id === tenant?.id ? 'active' : ''}
                  type="button"
                  onClick={() => {
                    onTenantSwitch?.(item)
                    setTenantOpen(false)
                  }}
                >
                  {item.name}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="profile-control">
          <button className="profile-chip" type="button" onClick={() => setUserOpen((value) => !value)}>
            <span className="profile-avatar">{(tenant?.slug?.[0] || 'B').toUpperCase()}</span>
            <span>
              <strong>{roleLabel}</strong>
              <small>{tenant?.slug || 'workspace'}</small>
            </span>
          </button>
          {userOpen && (
            <div className="topbar-menu profile-menu">
              <div className="menu-meta">
                <strong>{tenant?.name || 'TurkRAG'}</strong>
                <span>{tenant?.slug}</span>
              </div>
              <button type="button" onClick={onLogout} className="danger">
                <IconLogout /> Log out
              </button>
            </div>
          )}
        </div>
      </div>

      {(tenantOpen || userOpen) && (
        <button
          className="menu-scrim"
          type="button"
          aria-label="Close menu"
          onClick={() => {
            setTenantOpen(false)
            setUserOpen(false)
          }}
        />
      )}
    </header>
  )
}
