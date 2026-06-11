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
  { key: 'chat',      icon: <IconChat />,      label: 'Sohbet'   },
  { key: 'documents', icon: <IconDocs />,      label: 'Belgeler' },
  { key: 'analytics', icon: <IconAnalytics />, label: 'Analitik' },
  { key: 'admin',     icon: <IconAdmin />,     label: 'Yönetim'  },
]

function NavItem({ item, active, collapsed, onClick }) {
  return (
    <button
      onClick={onClick}
      title={collapsed ? item.label : undefined}
      className="btn"
      style={{
        width: '100%', justifyContent: collapsed ? 'center' : 'flex-start',
        padding: collapsed ? '9px 0' : '9px 12px',
        borderRadius: 'var(--radius-md)',
        background: active ? 'var(--accent-muted)' : 'transparent',
        color: active ? 'var(--accent)' : 'var(--text-2)',
        fontSize: '13px', fontWeight: active ? 600 : 400,
        gap: collapsed ? 0 : '10px',
        transition: 'background 0.12s, color 0.12s',
      }}
      onMouseEnter={(e) => { if (!active) { e.currentTarget.style.background = 'var(--surface-2)'; e.currentTarget.style.color = 'var(--text-1)' } }}
      onMouseLeave={(e) => { if (!active) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-2)' } }}
    >
      <span style={{ flexShrink: 0 }}>{item.icon}</span>
      {!collapsed && <span>{item.label}</span>}
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
    <aside style={{
      width: collapsed ? 'var(--sidebar-w-collapsed)' : 'var(--sidebar-w)',
      flexShrink: 0,
      background: 'var(--glass-bg)',
      backdropFilter: 'var(--glass-blur)',
      WebkitBackdropFilter: 'var(--glass-blur)',
      borderRight: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column',
      transition: 'width 0.25s cubic-bezier(0.16,1,0.3,1)',
      overflow: 'hidden',
    }}>
      {/* Nav items */}
      <nav style={{
        flex: 1, padding: '12px 8px',
        display: 'flex', flexDirection: 'column', gap: '2px',
        overflowY: 'auto', overflowX: 'hidden',
      }}>
        {navItems.map((item) => (
          <NavItem
            key={item.key}
            item={item}
            active={tab === item.key}
            collapsed={collapsed}
            onClick={() => onTabChange(item.key)}
          />
        ))}

        {/* Session history — chat tab only, not collapsed */}
        {tab === 'chat' && !collapsed && sessions?.length > 0 && (
          <>
            <div className="divider" style={{ margin: '8px 4px' }} />
            <div style={{
              fontSize: '10px', fontWeight: 700, color: 'var(--text-3)',
              letterSpacing: '0.08em', textTransform: 'uppercase',
              padding: '4px 8px 4px',
            }}>
              Geçmiş Sohbetler
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
              {sessions.map((s) => (
                <button
                  key={s.id}
                  onClick={() => onSessionSelect?.(s.id)}
                  className="btn"
                  style={{
                    width: '100%', justifyContent: 'flex-start', textAlign: 'left',
                    padding: '7px 10px', borderRadius: 'var(--radius-md)',
                    background: selectedSession === s.id ? 'var(--accent-muted)' : 'transparent',
                    color: selectedSession === s.id ? 'var(--accent)' : 'var(--text-2)',
                    fontSize: '12px', flexDirection: 'column', alignItems: 'flex-start', gap: '1px',
                  }}
                  onMouseEnter={(e) => { if (selectedSession !== s.id) e.currentTarget.style.background = 'var(--surface-2)' }}
                  onMouseLeave={(e) => { if (selectedSession !== s.id) e.currentTarget.style.background = 'transparent' }}
                >
                  <div style={{
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    width: '100%', fontWeight: selectedSession === s.id ? 600 : 400,
                  }}>
                    {s.preview || 'Sohbet'}
                  </div>
                  <div style={{ fontSize: '10px', color: 'var(--text-3)' }}>
                    {new Date(s.created_at).toLocaleDateString('tr-TR', { month: 'short', day: 'numeric' })}
                  </div>
                </button>
              ))}
            </div>
          </>
        )}
      </nav>

      {/* Bottom: upload + collapse */}
      <div style={{
        padding: '8px', borderTop: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column', gap: '4px',
      }}>
        {!collapsed && (
          <button
            onClick={onUploadClick}
            className="btn btn-outline"
            style={{ width: '100%', fontSize: '12px', padding: '8px 12px' }}
          >
            <IconUpload /> Belge Yükle
          </button>
        )}
        <button
          onClick={onCollapseToggle}
          className="btn btn-ghost"
          style={{
            width: '100%', fontSize: '11px', color: 'var(--text-3)',
            justifyContent: collapsed ? 'center' : 'flex-end',
            padding: '6px',
          }}
          title={collapsed ? 'Genişlet' : 'Daralt'}
        >
          {collapsed ? <IconExpand /> : <><IconCollapse /><span>Daralt</span></>}
        </button>
      </div>
    </aside>
  )
}
