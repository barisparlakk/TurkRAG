import React, { useEffect, useMemo, useRef, useState } from 'react'

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
  onRefresh,
  commands = [],
  notifications = [],
  onCommand,
  onNotificationSelect,
}) {
  const [userOpen, setUserOpen] = useState(false)
  const [tenantOpen, setTenantOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [notificationOpen, setNotificationOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const searchRef = useRef(null)
  const roleLabel = role === 'platform_admin' ? 'Platform' : role === 'admin' ? 'Admin' : 'Member'
  const filteredCommands = useMemo(() => {
    const term = searchTerm.trim().toLowerCase()
    if (!term) return commands
    return commands.filter((command) =>
      `${command.label} ${command.detail}`.toLowerCase().includes(term)
    )
  }, [commands, searchTerm])

  useEffect(() => {
    const onKeyDown = (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setSearchOpen(true)
        searchRef.current?.focus()
      }
      if (event.key === 'Escape') {
        setSearchOpen(false)
        setNotificationOpen(false)
        setTenantOpen(false)
        setUserOpen(false)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  const closeMenus = () => {
    setSearchOpen(false)
    setNotificationOpen(false)
    setTenantOpen(false)
    setUserOpen(false)
  }

  const runCommand = (command) => {
    onCommand?.(command)
    setSearchTerm('')
    closeMenus()
  }

  const selectNotification = (notification) => {
    onNotificationSelect?.(notification)
    closeMenus()
  }

  return (
    <header className="app-topbar">
      <div className="global-search">
        <IconSearch />
        <input
          ref={searchRef}
          type="search"
          value={searchTerm}
          placeholder="Sayfa ve işlem ara..."
          onChange={(event) => {
            setSearchTerm(event.target.value)
            setSearchOpen(true)
          }}
          onFocus={() => setSearchOpen(true)}
          aria-label="Panoda ara"
        />
        <kbd>⌘ K</kbd>
        {searchOpen && (
          <div className="command-menu" role="listbox" aria-label="Komut arama sonuçları">
            <div className="menu-meta">
              <strong>Git</strong>
              <span>{filteredCommands.length} işlem</span>
            </div>
            {filteredCommands.length ? filteredCommands.map((command) => (
              <button
                key={command.id}
                type="button"
                role="option"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => runCommand(command)}
              >
                <strong>{command.label}</strong>
                <span>{command.detail}</span>
              </button>
            )) : (
              <div className="topbar-empty">Eşleşen işlem yok</div>
            )}
          </div>
        )}
      </div>

      <div className="topbar-actions">
        <button className="topbar-icon refresh-control" type="button" onClick={onRefresh} title="Verileri yenile" aria-label="Verileri yenile">
          <IconRefresh />
        </button>
        <button className="topbar-icon" type="button" onClick={onThemeToggle} title={theme === 'dark' ? 'Açık tema' : 'Koyu tema'} aria-label={theme === 'dark' ? 'Açık temaya geç' : 'Koyu temaya geç'}>
          {theme === 'dark' ? <IconSun /> : <IconMoon />}
        </button>
        <button
          className={`topbar-icon ${notifications.length ? 'has-dot' : ''}`}
          type="button"
          title="Bildirimler"
          aria-label="Bildirimleri aç"
          onClick={() => {
            setNotificationOpen((value) => !value)
            setSearchOpen(false)
            setTenantOpen(false)
            setUserOpen(false)
          }}
        >
          <IconBell />
        </button>
        {notificationOpen && (
          <div className="topbar-menu notification-menu">
            <div className="menu-meta">
              <strong>Bildirimler</strong>
              <span>{notifications.length ? 'Çalışma alanı uyarıları' : 'Yeni bildirim yok'}</span>
            </div>
            {notifications.length ? notifications.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`notification-item tone-${item.tone || 'info'}`}
                onClick={() => selectNotification(item)}
              >
                <strong>{item.title}</strong>
                <span>{item.detail}</span>
              </button>
            )) : (
              <div className="topbar-empty">Yeni bildirim yok</div>
            )}
          </div>
        )}

        <div className="tenant-control">
          <button
            className="tenant-chip"
            type="button"
            onClick={() => tenants.length > 1 && setTenantOpen((value) => !value)}
            disabled={tenants.length <= 1}
            aria-haspopup={tenants.length > 1 ? 'menu' : undefined}
            aria-expanded={tenants.length > 1 ? tenantOpen : undefined}
            title={tenants.length > 1 ? 'Çalışma alanını değiştir' : 'Geçerli çalışma alanı'}
          >
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
                <IconLogout /> Çıkış yap
              </button>
            </div>
          )}
        </div>
      </div>

      {(tenantOpen || userOpen || searchOpen || notificationOpen) && (
        <button
          className="menu-scrim"
          type="button"
          aria-label="Close menu"
          onClick={closeMenus}
        />
      )}
    </header>
  )
}
