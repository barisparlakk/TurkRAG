import React, { useState } from 'react'

function Icon({ name }) {
  const common = {
    width: 17,
    height: 17,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
  }
  const paths = {
    dashboard: <><rect x="3" y="3" width="7" height="8" rx="1.5" /><rect x="14" y="3" width="7" height="5" rx="1.5" /><rect x="14" y="12" width="7" height="9" rx="1.5" /><rect x="3" y="15" width="7" height="6" rx="1.5" /></>,
    ask: <><path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z" /><path d="M8 9h8M8 13h5" /></>,
    documents: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /><path d="M8 13h8M8 17h6" /></>,
    collections: <><path d="M4 7h16" /><path d="M4 12h16" /><path d="M4 17h16" /><rect x="3" y="4" width="18" height="16" rx="2" /></>,
    history: <><path d="M3 12a9 9 0 1 0 3-6.7" /><path d="M3 4v5h5" /><path d="M12 7v6l4 2" /></>,
    analytics: <><path d="M4 19V5" /><path d="M4 19h16" /><path d="M8 15l3-4 3 2 4-7" /></>,
    jobs: <><path d="M4 4h16v5H4z" /><path d="M4 15h16v5H4z" /><path d="M8 9v6M16 9v6" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6V21a2 2 0 1 1-4 0v-.2a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1A2 2 0 1 1 4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.6-1H3a2 2 0 1 1 0-4h.2a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1A2 2 0 1 1 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3h.1a1.7 1.7 0 0 0 1-1.6V3a2 2 0 1 1 4 0v.2a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1A2 2 0 1 1 19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9v.1a1.7 1.7 0 0 0 1.6 1h.1a2 2 0 1 1 0 4H21a1.7 1.7 0 0 0-1.6 1z" /></>,
    system: <><path d="M12 2l8 4v6c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10V6z" /><path d="M9 12l2 2 4-5" /></>,
  }
  return <svg {...common}>{paths[name]}</svg>
}

const MAIN_NAV = [
  { key: 'dashboard', icon: 'dashboard', label: 'Pano' },
  { key: 'chat', icon: 'ask', label: 'Belgelere Sor' },
  { key: 'documents', icon: 'documents', label: 'Belgeler' },
  { key: 'collections', icon: 'collections', label: 'Koleksiyonlar' },
  { key: 'history', icon: 'history', label: 'Geçmiş' },
  { key: 'analytics', icon: 'analytics', label: 'Analitik' },
]

const SYSTEM_NAV = [
  { key: 'jobs', icon: 'jobs', label: 'İçe Aktarım' },
  { key: 'settings', icon: 'settings', label: 'Ayarlar' },
  { key: 'system', icon: 'system', label: 'Sistem Durumu' },
]

const MOBILE_NAV = MAIN_NAV.filter((item) => ['dashboard', 'chat', 'documents', 'history'].includes(item.key))
const MOBILE_MORE_NAV = [
  ...MAIN_NAV.filter((item) => item.key === 'analytics'),
  ...SYSTEM_NAV,
]

function NavButton({ item, active, onClick }) {
  return (
    <button
      className={`nav-link ${active ? 'active' : ''}`}
      onClick={onClick}
      title={item.label}
      type="button"
    >
      <span className="nav-link-icon"><Icon name={item.icon} /></span>
      <span>{item.label}</span>
    </button>
  )
}

export function Sidebar({ tab, onTabChange, tenant, health }) {
  const [mobileMoreOpen, setMobileMoreOpen] = useState(false)
  const selectTab = (key) => {
    onTabChange(key)
    setMobileMoreOpen(false)
  }
  const isMoreActive = MOBILE_MORE_NAV.some((item) => item.key === tab)

  return (
    <aside className="app-sidebar">
      <div className="sidebar-brand">
        <div className="brand-mark">
          <img src="/logo-dark.png" alt="" />
        </div>
        <div>
          <strong>TurkRAG</strong>
          <span>AI-Powered Document Intelligence</span>
        </div>
      </div>

      <nav className="sidebar-nav desktop-nav" aria-label="Primary navigation">
        {MAIN_NAV.map((item) => (
          <NavButton
            key={item.key}
            item={item}
            active={tab === item.key}
            onClick={() => selectTab(item.key)}
          />
        ))}
      </nav>

      <div className="sidebar-section-title">Sistem</div>
      <nav className="sidebar-nav compact desktop-nav" aria-label="System navigation">
        {SYSTEM_NAV.map((item) => (
          <NavButton
            key={item.key}
            item={item}
            active={tab === item.key}
            onClick={() => selectTab(item.key)}
          />
        ))}
      </nav>

      <nav className="sidebar-nav mobile-nav" aria-label="Mobil gezinme">
        {MOBILE_NAV.map((item) => (
          <NavButton
            key={item.key}
            item={item}
            active={tab === item.key}
            onClick={() => selectTab(item.key)}
          />
        ))}
        <button
          className={`nav-link ${isMoreActive || mobileMoreOpen ? 'active' : ''}`}
          type="button"
          aria-expanded={mobileMoreOpen}
          aria-controls="mobile-more-navigation"
          onClick={() => setMobileMoreOpen((value) => !value)}
        >
          <span className="nav-link-icon" aria-hidden="true">•••</span>
          <span>Diğer</span>
        </button>
      </nav>

      {mobileMoreOpen && (
        <div className="mobile-nav-menu" id="mobile-more-navigation" aria-label="Diğer sayfalar">
          {MOBILE_MORE_NAV.map((item) => (
            <NavButton
              key={item.key}
              item={item}
              active={tab === item.key}
              onClick={() => selectTab(item.key)}
            />
          ))}
        </div>
      )}

      <div className="sidebar-status">
        <div>
          <span>Sistem Durumu</span>
          <strong>{health?.status === 'ok' ? 'Çalışıyor' : health ? 'Kısıtlı' : 'Kontrol ediliyor'}</strong>
        </div>
        <div className={`status-spark ${health?.status === 'ok' ? 'ok' : 'warn'}`} aria-hidden="true">
          <i /><i /><i /><i /><i /><i /><i /><i />
        </div>
        <small>{tenant?.name || tenant?.slug || 'Tenant scoped'}</small>
      </div>
    </aside>
  )
}
