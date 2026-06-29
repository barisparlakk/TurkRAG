import React from 'react'

const IconChat = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
  </svg>
)
const IconDocs = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
    <line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
  </svg>
)
const IconAnalytics = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="20" x2="18" y2="10"/>
    <line x1="12" y1="20" x2="12" y2="4"/>
    <line x1="6" y1="20" x2="6" y2="14"/>
    <line x1="2" y1="20" x2="22" y2="20"/>
  </svg>
)
const IconAdmin = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3"/>
    <path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"/>
  </svg>
)
const IconUpload = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="16 16 12 12 8 16"/>
    <line x1="12" y1="12" x2="12" y2="21"/>
    <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/>
  </svg>
)
const IconCollapse = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="15 18 9 12 15 6"/>
  </svg>
)
const IconExpand = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="9 18 15 12 9 6"/>
  </svg>
)

const NAV_ITEMS = [
  { key: 'chat',      icon: <IconChat />,      label: 'Sorgu',     description: 'Yanıt ve kanıt' },
  { key: 'documents', icon: <IconDocs />,      label: 'Kaynaklar', description: 'İndeks ve işler' },
  { key: 'analytics', icon: <IconAnalytics />, label: 'Kalite',    description: 'Kullanım ve eval' },
  { key: 'admin',     icon: <IconAdmin />,     label: 'Yetki',     description: 'Tenant ve sistem' },
]

function NavItem({ item, active, collapsed, onClick }) {
  return (
    <button
      onClick={onClick}
      title={collapsed ? item.label : undefined}
      className={`sidebar-nav-item ${active ? 'active' : ''} ${collapsed ? 'collapsed' : ''}`}
    >
      <span className="sidebar-nav-icon">{item.icon}</span>
      {!collapsed && (
        <span className="sidebar-nav-copy">
          <span className="sidebar-nav-label">{item.label}</span>
          <span className="sidebar-nav-description">{item.description}</span>
        </span>
      )}
    </button>
  )
}

export function Sidebar({
  tab,
  onTabChange,
  onUploadClick,
  collapsed,
  onCollapseToggle,
  sessions,
  selectedSession,
  onSessionSelect,
  showAdmin = false,
}) {
  const navItems = showAdmin ? NAV_ITEMS : NAV_ITEMS.filter((item) => item.key !== 'admin')

  return (
    <aside className={`app-sidebar ${collapsed ? 'collapsed' : ''}`}>
      <nav className="sidebar-nav">
        {!collapsed && <div className="sidebar-section-label">Operasyon</div>}
        {navItems.map((item) => (
          <NavItem
            key={item.key}
            item={item}
            active={tab === item.key}
            collapsed={collapsed}
            onClick={() => onTabChange(item.key)}
          />
        ))}

        {tab === 'chat' && !collapsed && sessions?.length > 0 && (
          <>
            <div className="divider" style={{ margin: '8px 4px' }} />
            <div className="sidebar-section-label">Sorgu fişleri</div>
            <div className="session-list">
              {sessions.map((s, index) => (
                <button
                  key={s.id}
                  onClick={() => onSessionSelect?.(s.id)}
                  className={`session-row ${selectedSession === s.id ? 'active' : ''}`}
                >
                  <div className="session-index">F{String(index + 1).padStart(2, '0')}</div>
                  <div className="session-title">
                    {s.preview || 'Sohbet'}
                  </div>
                  <div className="session-date">
                    {new Date(s.created_at).toLocaleDateString('tr-TR', { month: 'short', day: 'numeric' })}
                  </div>
                </button>
              ))}
            </div>
          </>
        )}
      </nav>

      <div className="sidebar-footer">
        {!collapsed && (
          <button
            onClick={onUploadClick}
            className="btn btn-outline sidebar-upload"
            title="Belge yükle"
          >
            <IconUpload /> Yükle
          </button>
        )}
        <button
          onClick={onCollapseToggle}
          className="sidebar-collapse"
          title={collapsed ? 'Genişlet' : 'Daralt'}
        >
          {collapsed ? <IconExpand /> : <IconCollapse />}
        </button>
      </div>
    </aside>
  )
}
