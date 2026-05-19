import React, { useState, useEffect } from 'react'
import { ChatWindow } from './components/ChatWindow.jsx'
import { DocumentUpload } from './components/DocumentUpload.jsx'
import { AnalyticsDashboard } from './components/AnalyticsDashboard.jsx'
import AdminPanel from './components/AdminPanel.jsx'
import { api, setToken } from './api/client.js'

const IconChat = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
  </svg>
)

const IconDocs = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
    <line x1="16" y1="13" x2="8" y2="13"/>
    <line x1="16" y1="17" x2="8" y2="17"/>
    <polyline points="10 9 9 9 8 9"/>
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
    <path d="M15.54 8.46a5 5 0 0 1 0 7.07M8.46 8.46a5 5 0 0 0 0 7.07"/>
  </svg>
)
const IconLogout = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
    <polyline points="16 17 21 12 16 7"/>
    <line x1="21" y1="12" x2="9" y2="12"/>
  </svg>
)

/* ── Logo ──────────────────────────────────────────────── */
function Logo() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '24px 20px 20px' }}>
      <div style={{
        width: 34, height: 34, borderRadius: 10,
        background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        boxShadow: '0 0 16px rgba(99,102,241,0.4)',
        flexShrink: 0,
      }}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
      </div>
      <div>
        <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-1)', letterSpacing: '-0.01em' }}>TurkRAG</div>
        <div style={{ fontSize: '10px', color: 'var(--text-3)', fontWeight: 500, letterSpacing: '0.04em', textTransform: 'uppercase' }}>Belge Asistanı</div>
      </div>
    </div>
  )
}

/* ── Nav item ──────────────────────────────────────────── */
function NavItem({ icon, label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className="btn"
      style={{
        width: '100%', justifyContent: 'flex-start',
        padding: '9px 14px', gap: '10px',
        borderRadius: 'var(--radius-md)',
        background: active ? 'var(--accent-muted)' : 'transparent',
        color: active ? 'var(--accent-hover)' : 'var(--text-2)',
        fontSize: '13.5px', fontWeight: active ? 600 : 400,
        borderLeft: active ? '2px solid var(--accent)' : '2px solid transparent',
        transition: 'all 0.15s',
      }}
      onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = 'var(--surface-3)' }}
      onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = 'transparent' }}
    >
      {icon}
      {label}
    </button>
  )
}

/* ── Login ─────────────────────────────────────────────── */
function LoginPage({ onLogin }) {
  const [loginSlug, setLoginSlug] = useState('')
  const [loginError, setLoginError] = useState('')
  const [tenants, setTenants] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.listTenants().then(setTenants).catch(() => setTenants([]))
  }, [])

  const handleLogin = async (e) => {
    e.preventDefault()
    const slug = loginSlug.trim()
    if (!slug) { setLoginError('Lütfen bir çalışma alanı seçiniz'); return }
    setLoading(true); setLoginError('')
    try {
      const tenant = await api.getTenantBySlug(slug)
      const data = await api.getToken(tenant.id, 'demo-user', 'member')
      setToken(data.access_token)
      onLogin({ slug, id: tenant.id })
    } catch (err) {
      setLoginError(`Giriş başarısız: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'radial-gradient(ellipse 80% 60% at 50% -10%, rgba(99,102,241,0.18) 0%, var(--bg) 70%)',
      padding: '24px',
    }}>
      {/* Subtle grid pattern */}
      <div style={{
        position: 'fixed', inset: 0, opacity: 0.03, pointerEvents: 'none',
        backgroundImage: 'linear-gradient(var(--text-1) 1px, transparent 1px), linear-gradient(90deg, var(--text-1) 1px, transparent 1px)',
        backgroundSize: '40px 40px',
      }} />

      <div className="fade-up" style={{
        width: '100%', maxWidth: '400px',
        background: 'var(--surface-1)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-xl)',
        padding: '40px 36px',
        boxShadow: '0 0 0 1px var(--border-soft), var(--shadow-lg)',
        position: 'relative', zIndex: 1,
      }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div style={{
            width: 56, height: 56, margin: '0 auto 16px',
            borderRadius: 16,
            background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 0 32px rgba(99,102,241,0.35)',
          }}>
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
          </div>
          <h1 style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text-1)', letterSpacing: '-0.02em' }}>
            TurkRAG
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-2)', marginTop: '6px' }}>
            Türkçe Kurumsal Belge Asistanı
          </p>
        </div>

        <form onSubmit={handleLogin}>
          <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)', letterSpacing: '0.04em', textTransform: 'uppercase', display: 'block', marginBottom: '8px' }}>
            Çalışma Alanı
          </label>
          {tenants.length > 0 ? (
            <select
              value={loginSlug}
              onChange={(e) => setLoginSlug(e.target.value)}
              className="input-field"
              style={{ marginBottom: '20px', appearance: 'none' }}
            >
              <option value="">— Çalışma alanı seçin —</option>
              {tenants.map((t) => (
                <option key={t.id} value={t.slug}>{t.name} · {t.slug}</option>
              ))}
            </select>
          ) : (
            <input
              type="text"
              value={loginSlug}
              onChange={(e) => setLoginSlug(e.target.value)}
              placeholder="ornek: acme-sirket"
              className="input-field"
              style={{ marginBottom: '20px' }}
            />
          )}

          {loginError && (
            <div style={{
              background: 'var(--error-muted)', border: '1px solid rgba(239,68,68,0.2)',
              color: 'var(--error)', fontSize: '13px',
              borderRadius: 'var(--radius-md)', padding: '10px 12px',
              marginBottom: '16px',
            }}>
              {loginError}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="btn btn-primary"
            style={{ width: '100%', padding: '12px', fontSize: '14px', borderRadius: 'var(--radius-md)' }}
          >
            {loading ? (
              <span style={{ width: 16, height: 16, border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', borderRadius: '50%', display: 'inline-block', animation: 'spin 0.7s linear infinite' }} />
            ) : 'Giriş Yap →'}
          </button>
        </form>

        <p style={{ textAlign: 'center', fontSize: '11px', color: 'var(--text-3)', marginTop: '24px' }}>
          KVKK uyumlu · Tamamen şirket içi
        </p>
      </div>
    </div>
  )
}

/* ── Session history panel (shown inside sidebar when on chat tab) ─────────── */
function SessionHistory({ selectedId, onSelect, refreshTrigger }) {
  const [sessions, setSessions] = useState([])

  useEffect(() => {
    api.listSessions(20)
      .then(setSessions)
      .catch(() => {})
  }, [refreshTrigger])

  if (!sessions.length) return null

  return (
    <div style={{ padding: '0 10px', marginTop: '4px' }}>
      <div style={{
        fontSize: '10px', fontWeight: 600, color: 'var(--text-3)',
        letterSpacing: '0.08em', textTransform: 'uppercase', padding: '4px 6px 6px',
      }}>
        Geçmiş Sohbetler
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1px', maxHeight: 220, overflowY: 'auto' }}>
        {sessions.map((s) => (
          <button
            key={s.id}
            onClick={() => onSelect(s.id)}
            className="btn"
            style={{
              width: '100%', justifyContent: 'flex-start', textAlign: 'left',
              padding: '7px 10px', borderRadius: 'var(--radius-md)',
              background: selectedId === s.id ? 'var(--accent-muted)' : 'transparent',
              color: selectedId === s.id ? 'var(--accent-hover)' : 'var(--text-2)',
              fontSize: '12px', fontWeight: selectedId === s.id ? 600 : 400,
              borderLeft: `2px solid ${selectedId === s.id ? 'var(--accent)' : 'transparent'}`,
              overflow: 'hidden',
            }}
            onMouseEnter={(e) => { if (selectedId !== s.id) e.currentTarget.style.background = 'var(--surface-3)' }}
            onMouseLeave={(e) => { if (selectedId !== s.id) e.currentTarget.style.background = 'transparent' }}
          >
            <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {s.preview}
            </div>
            <div style={{ fontSize: '10px', color: 'var(--text-3)', marginTop: '1px' }}>
              {new Date(s.created_at).toLocaleDateString('tr-TR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

/* ── Main app layout ───────────────────────────────────── */
export default function App() {
  const [tenant, setTenant] = useState(null)
  const [tab, setTab] = useState('chat')
  const [selectedSession, setSelectedSession] = useState(null)
  const [sessionRefresh, setSessionRefresh] = useState(0)

  if (!tenant) {
    return <LoginPage onLogin={setTenant} />
  }

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Sidebar */}
      <aside style={{
        width: 'var(--sidebar-w)', flexShrink: 0,
        background: 'var(--surface-1)',
        borderRight: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column',
      }}>
        <Logo />

        {/* Divider */}
        <div style={{ height: 1, background: 'var(--border)', margin: '0 16px 16px' }} />

        {/* Nav */}
        <nav style={{ padding: '0 10px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
          <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--text-3)', letterSpacing: '0.08em', textTransform: 'uppercase', padding: '4px 6px 8px' }}>
            Ana Menü
          </div>
          <NavItem icon={<IconChat />} label="Sohbet" active={tab === 'chat'} onClick={() => setTab('chat')} />
          <NavItem icon={<IconDocs />} label="Belgeler" active={tab === 'documents'} onClick={() => setTab('documents')} />
          <NavItem icon={<IconAnalytics />} label="Analitik" active={tab === 'analytics'} onClick={() => setTab('analytics')} />
          <NavItem icon={<IconAdmin />} label="Yönetim" active={tab === 'admin'} onClick={() => setTab('admin')} />
        </nav>

        {/* Session history — only visible on chat tab */}
        {tab === 'chat' && (
          <>
            <div style={{ height: 1, background: 'var(--border)', margin: '10px 16px 6px' }} />
            <SessionHistory
              selectedId={selectedSession}
              onSelect={(id) => { setSelectedSession(id); setTab('chat') }}
              refreshTrigger={sessionRefresh}
            />
          </>
        )}

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Tenant info + logout */}
        <div style={{ padding: '12px 14px 20px', borderTop: '1px solid var(--border)' }}>
          <div style={{
            background: 'var(--surface-2)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)', padding: '10px 12px',
            marginBottom: '10px',
          }}>
            <div style={{ fontSize: '10px', color: 'var(--text-3)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '4px' }}>
              Çalışma Alanı
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--success)', boxShadow: '0 0 6px var(--success)', flexShrink: 0 }} />
              <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {tenant.slug}
              </span>
            </div>
          </div>
          <button
            onClick={() => { setToken(''); setTenant(null) }}
            className="btn btn-ghost"
            style={{ width: '100%', justifyContent: 'flex-start', gap: '8px', fontSize: '13px', color: 'var(--text-3)' }}
          >
            <IconLogout /> Çıkış Yap
          </button>
        </div>
      </aside>

      {/* Content */}
      <main style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', background: 'var(--bg)' }}>
        {/* Top bar */}
        <header style={{
          height: 52, flexShrink: 0,
          borderBottom: '1px solid var(--border)',
          background: 'var(--surface-1)',
          display: 'flex', alignItems: 'center',
          padding: '0 24px', gap: '12px',
        }}>
          <h2 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-1)' }}>
            {{ chat: 'Sohbet', documents: 'Belge Yönetimi', analytics: 'Analitik', admin: 'Yönetim Paneli' }[tab]}
          </h2>
          <div style={{ marginLeft: 'auto', fontSize: '12px', color: 'var(--text-3)' }}>
            {{ chat: 'Belgelerinize akıllı sorular sorun', documents: 'Belgelerinizi yükleyin ve yönetin', analytics: 'Sorgu istatistikleri ve kullanım özeti', admin: 'Sistem yönetimi ve kiracı ayarları' }[tab]}
          </div>
        </header>

        {/* Page content — both always mounted to preserve chat history */}
        <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: tab === 'chat' ? 'flex' : 'none', flex: 1, overflow: 'hidden', flexDirection: 'column' }}>
            <ChatWindow
              selectedSession={selectedSession}
              onSessionChange={setSelectedSession}
              onNewSession={() => setSessionRefresh((n) => n + 1)}
            />
          </div>
          <div style={{ display: tab === 'documents' ? 'flex' : 'none', flex: 1, overflowY: 'auto', flexDirection: 'column' }}>
            <div style={{ padding: '24px', maxWidth: 760, width: '100%', margin: '0 auto' }}>
              <DocumentUpload />
            </div>
          </div>
          <div style={{ display: tab === 'analytics' ? 'flex' : 'none', flex: 1, overflowY: 'auto', flexDirection: 'column' }}>
            <div style={{ padding: '24px', maxWidth: 900, width: '100%', margin: '0 auto' }}>
              <AnalyticsDashboard />
            </div>
          </div>
          <div style={{ display: tab === 'admin' ? 'flex' : 'none', flex: 1, overflowY: 'auto', flexDirection: 'column' }}>
            <div style={{ padding: '24px', maxWidth: 900, width: '100%', margin: '0 auto' }}>
              <AdminPanel />
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
