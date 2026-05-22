import React, { useState, useEffect } from 'react'
import { ChatWindow } from './components/ChatWindow.jsx'
import { DocumentUpload } from './components/DocumentUpload.jsx'
import { AnalyticsDashboard } from './components/AnalyticsDashboard.jsx'
import AdminPanel from './components/AdminPanel.jsx'
import { Header } from './components/Header.jsx'
import { Sidebar } from './components/Sidebar.jsx'
import { SourcesPanel } from './components/SourcesPanel.jsx'
import { ToastProvider } from './components/Toast.jsx'
import { api, setToken } from './api/client.js'

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
      onLogin({ slug, id: tenant.id, name: tenant.name || tenant.slug })
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
      background: 'var(--bg)',
      padding: '24px',
    }}>
      <div className="fade-up" style={{
        width: '100%', maxWidth: '400px',
        background: 'var(--glass-bg)',
        backdropFilter: 'var(--glass-blur)',
        WebkitBackdropFilter: 'var(--glass-blur)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-xl)',
        padding: '40px 36px',
        boxShadow: 'var(--shadow-xl)',
        position: 'relative', zIndex: 1,
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div style={{ width: 80, height: 80, margin: '0 auto 16px' }}>
            <img src="/logo-light.png" className="logo-light" style={{ width: 80, height: 80, objectFit: 'contain' }} alt="TurkRAG" />
            <img src="/logo-dark.png"  className="logo-dark"  style={{ width: 80, height: 80, objectFit: 'contain' }} alt="TurkRAG" />
          </div>
          <h1 style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text-1)', letterSpacing: '-0.02em' }}>
            TurkRAG
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-2)', marginTop: '6px' }}>
            Türkçe Kurumsal Belge Asistanı
          </p>
        </div>

        <form onSubmit={handleLogin}>
          <label style={{
            fontSize: '12px', fontWeight: 600, color: 'var(--text-2)',
            letterSpacing: '0.04em', textTransform: 'uppercase',
            display: 'block', marginBottom: '8px',
          }}>
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
              <span style={{
                width: 16, height: 16, border: '2px solid rgba(255,255,255,0.3)',
                borderTopColor: '#fff', borderRadius: '50%', display: 'inline-block',
                animation: 'spin 0.7s linear infinite',
              }} />
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

/* ── Main app ──────────────────────────────────────────── */
export default function App() {
  const [tenant, setTenant] = useState(() => {
    try {
      const saved = localStorage.getItem('turkrag_tenant')
      return saved ? JSON.parse(saved) : null
    } catch { return null }
  })
  const [tenants, setTenants] = useState([])
  const [tab, setTab] = useState('chat')
  const [selectedSession, setSelectedSession] = useState(null)
  const [sessionRefresh, setSessionRefresh] = useState(0)
  const [sessions, setSessions] = useState([])
  const [citations, setCitations] = useState([])
  const [attribution, setAttribution] = useState(null)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [theme, setTheme] = useState(() => localStorage.getItem('turkrag_theme') || 'light')

  /* Apply theme to <html> */
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('turkrag_theme', theme)
  }, [theme])

  /* Validate restored session — if token expired, force re-login */
  useEffect(() => {
    if (!tenant) return
    api.listSessions(1).catch(() => {
      setToken('')
      setTenant(null)
      localStorage.removeItem('turkrag_tenant')
    })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  /* Load tenant list for header switcher */
  useEffect(() => {
    if (!tenant) return
    api.listTenants().then(setTenants).catch(() => {})
  }, [tenant])

  /* Load session history */
  useEffect(() => {
    if (!tenant) return
    api.listSessions(30).then(setSessions).catch(() => {})
  }, [tenant, sessionRefresh])

  const handleLogout = () => {
    setToken('')
    setTenant(null)
    localStorage.removeItem('turkrag_tenant')
    setSessions([])
    setCitations([])
    setSelectedSession(null)
  }

  const handleTenantSwitch = async (t) => {
    try {
      const data = await api.getToken(t.id, 'demo-user', 'member')
      setToken(data.access_token)
      const next = { slug: t.slug, id: t.id, name: t.name }
      setTenant(next)
      localStorage.setItem('turkrag_tenant', JSON.stringify(next))
      setSelectedSession(null)
      setCitations([])
      setSessionRefresh((n) => n + 1)
    } catch {}
  }

  if (!tenant) {
    return (
      <ToastProvider>
        <LoginPage onLogin={(t) => {
          setTenant(t)
          setTenants([t])
          localStorage.setItem('turkrag_tenant', JSON.stringify(t))
        }} />
      </ToastProvider>
    )
  }

  return (
    <ToastProvider>
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>

        {/* ── Header ── */}
        <Header
          tenant={tenant}
          tenants={tenants}
          onTenantSwitch={handleTenantSwitch}
          onLogout={handleLogout}
          theme={theme}
          onThemeToggle={() => setTheme((t) => t === 'dark' ? 'light' : 'dark')}
        />

        {/* ── Body row ── */}
        <div style={{ flex: 1, overflow: 'hidden', display: 'flex' }}>

          {/* ── Sidebar ── */}
          <Sidebar
            tab={tab}
            onTabChange={(t) => { setTab(t); if (t !== 'chat') setCitations([]) }}
            onUploadClick={() => setTab('documents')}
            collapsed={sidebarCollapsed}
            onCollapseToggle={() => setSidebarCollapsed((v) => !v)}
            sessions={sessions}
            selectedSession={selectedSession}
            onSessionSelect={(id) => { setSelectedSession(id); setTab('chat') }}
          />

          {/* ── Main content ── */}
          <main style={{ flex: 1, overflow: 'hidden', display: 'flex', background: 'var(--bg)' }}>

            {/* Chat */}
            <div style={{
              display: tab === 'chat' ? 'flex' : 'none',
              flex: 1, overflow: 'hidden', flexDirection: 'column',
            }}>
              <ChatWindow
                selectedSession={selectedSession}
                onSessionChange={setSelectedSession}
                onNewSession={() => setSessionRefresh((n) => n + 1)}
                onCitationsChange={(cits, attr) => { setCitations(cits); setAttribution(attr || null) }}
              />
            </div>

            {/* Documents */}
            <div style={{
              display: tab === 'documents' ? 'flex' : 'none',
              flex: 1, overflowY: 'auto', flexDirection: 'column',
            }}>
              <div style={{ padding: '28px', maxWidth: 760, width: '100%', margin: '0 auto' }}>
                <DocumentUpload />
              </div>
            </div>

            {/* Analytics */}
            <div style={{
              display: tab === 'analytics' ? 'flex' : 'none',
              flex: 1, overflowY: 'auto', flexDirection: 'column',
            }}>
              <div style={{ padding: '28px', maxWidth: 900, width: '100%', margin: '0 auto' }}>
                <AnalyticsDashboard />
              </div>
            </div>

            {/* Admin */}
            <div style={{
              display: tab === 'admin' ? 'flex' : 'none',
              flex: 1, overflowY: 'auto', flexDirection: 'column',
            }}>
              <div style={{ padding: '28px', maxWidth: 900, width: '100%', margin: '0 auto' }}>
                <AdminPanel />
              </div>
            </div>
          </main>

          {/* ── Sources panel — chat tab only ── */}
          {tab === 'chat' && (
            <SourcesPanel citations={citations} attribution={attribution} />
          )}
        </div>
      </div>
    </ToastProvider>
  )
}
