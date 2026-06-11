import React, { useEffect, useState } from 'react'
import { ChatWindow } from './components/ChatWindow.jsx'
import { DocumentUpload } from './components/DocumentUpload.jsx'
import { AnalyticsDashboard } from './components/AnalyticsDashboard.jsx'
import AdminPanel from './components/AdminPanel.jsx'
import { Header } from './components/Header.jsx'
import { Sidebar } from './components/Sidebar.jsx'
import { SourcesPanel } from './components/SourcesPanel.jsx'
import { ToastProvider } from './components/Toast.jsx'
import { api, getTokenPayload, getToken, setToken } from './api/client.js'

const MOCK_ADMIN_EMAIL = 'baris@dev.com'
const MOCK_ADMIN_PASSWORD = '1234'
const AUTH_STORAGE_KEY = 'turkrag_auth'

function loadStoredJSON(key) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function isTokenExpired(payload) {
  return !payload?.exp || payload.exp * 1000 <= Date.now()
}

/* ── Login ─────────────────────────────────────────────── */
function LoginPage({ onLogin }) {
  const [mode, setMode] = useState('member')
  const [memberSlug, setMemberSlug] = useState('')
  const [adminSlug, setAdminSlug] = useState('')
  const [adminEmail, setAdminEmail] = useState(MOCK_ADMIN_EMAIL)
  const [adminPassword, setAdminPassword] = useState(MOCK_ADMIN_PASSWORD)
  const [loginError, setLoginError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleMemberLogin = async (e) => {
    e.preventDefault()
    const slug = memberSlug.trim()
    if (!slug) {
      setLoginError('Kullanıcı girişi için çalışma alanı slug alanı zorunludur.')
      return
    }

    setLoading(true)
    setLoginError('')
    try {
      const tenant = await api.getTenantBySlug(slug)
      const data = await api.getToken(tenant.id, 'demo-user', 'member')
      setToken(data.access_token)
      onLogin({
        tenant: { slug: tenant.slug, id: tenant.id, name: tenant.name || tenant.slug },
        auth: {
          loginMode: 'member',
          role: 'member',
          userId: 'demo-user',
        },
      })
    } catch (err) {
      setLoginError(`Kullanıcı girişi başarısız: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleAdminLogin = async (e) => {
    e.preventDefault()
    const slug = adminSlug.trim()
    if (!slug) {
      setLoginError('Admin girişi için yönetilecek çalışma alanı slug alanı zorunludur.')
      return
    }

    setLoading(true)
    setLoginError('')
    try {
      const data = await api.mockLogin(slug, adminEmail.trim(), adminPassword)
      setToken(data.access_token)
      onLogin({
        tenant: {
          slug: data.tenant.slug,
          id: data.tenant.id,
          name: data.tenant.name || data.tenant.slug,
        },
        auth: {
          loginMode: 'admin',
          role: 'admin',
          userId: data.user.email,
          email: data.user.email,
        },
      })
    } catch (err) {
      setLoginError(`Admin girişi başarısız: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-shell">
      <div className="login-stage fade-up">
        <section className="login-hero glass">
          <div className="login-badge">TurkRAG access control</div>
          <h1>Tek giriş ekranı yerine rol bazlı giriş akışı</h1>
          <p>
            Kullanıcılar yalnızca kendi çalışma alanına erişsin, admin ise tenant yönetimi
            ve operasyon panellerine kontrollü biçimde girebilsin.
          </p>

          <div className="login-highlights">
            <div className="login-highlight">
              <span>Üye oturumu</span>
              <strong>Belge sorgulama, yükleme, sohbet</strong>
            </div>
            <div className="login-highlight">
              <span>Admin oturumu</span>
              <strong>Tenant listeleme, sistem yönetimi, değerlendirme</strong>
            </div>
          </div>

          <div className="login-admin-note">
            <div className="login-admin-note-label">Mock admin credentials</div>
            <code>{MOCK_ADMIN_EMAIL}</code>
            <code>{MOCK_ADMIN_PASSWORD}</code>
          </div>
        </section>

        <section className="login-panel glass">
          <div className="login-brand">
            <div className="login-brand-logo">
              <img src="/logo-light.png" className="logo-light" alt="TurkRAG" />
              <img src="/logo-dark.png" className="logo-dark" alt="TurkRAG" />
            </div>
            <div>
              <div className="login-brand-kicker">Türkçe Kurumsal Belge Asistanı</div>
              <h2>Giriş merkezi</h2>
            </div>
          </div>

          <div className="login-mode-switch" role="tablist" aria-label="Giriş modu">
            <button
              type="button"
              className={`login-mode-chip ${mode === 'member' ? 'active' : ''}`}
              onClick={() => {
                setMode('member')
                setLoginError('')
              }}
            >
              Kullanıcı girişi
            </button>
            <button
              type="button"
              className={`login-mode-chip ${mode === 'admin' ? 'active' : ''}`}
              onClick={() => {
                setMode('admin')
                setLoginError('')
              }}
            >
              Admin girişi
            </button>
          </div>

          {mode === 'member' ? (
            <form onSubmit={handleMemberLogin} className="login-form">
              <div className="login-form-copy">
                <h3>Çalışma alanına kullanıcı olarak gir</h3>
                <p>Bu akış belge yükleme, sohbet ve kaynak inceleme işlemleri için member token üretir.</p>
              </div>

              <label className="login-label">
                Çalışma alanı slug
                <input
                  type="text"
                  value={memberSlug}
                  onChange={(e) => setMemberSlug(e.target.value)}
                  placeholder="ornek: acme-sirket"
                  className="input-field"
                />
              </label>

              {loginError && <div className="login-error">{loginError}</div>}

              <button type="submit" disabled={loading} className="btn btn-primary login-submit">
                {loading ? 'Giriş hazırlanıyor...' : 'Kullanıcı olarak devam et'}
              </button>
            </form>
          ) : (
            <form onSubmit={handleAdminLogin} className="login-form">
              <div className="login-form-copy">
                <h3>Yönetim konsoluna admin olarak gir</h3>
                <p>Bu akış backend tarafında mock admin doğrulaması yapar ve admin token döndürür.</p>
              </div>

              <label className="login-label">
                Yönetilecek çalışma alanı slug
                <input
                  type="text"
                  value={adminSlug}
                  onChange={(e) => setAdminSlug(e.target.value)}
                  placeholder="ornek: acme-sirket"
                  className="input-field"
                />
              </label>

              <div className="login-grid-two">
                <label className="login-label">
                  Email
                  <input
                    type="email"
                    value={adminEmail}
                    onChange={(e) => setAdminEmail(e.target.value)}
                    placeholder={MOCK_ADMIN_EMAIL}
                    className="input-field"
                  />
                </label>
                <label className="login-label">
                  Şifre
                  <input
                    type="password"
                    value={adminPassword}
                    onChange={(e) => setAdminPassword(e.target.value)}
                    placeholder={MOCK_ADMIN_PASSWORD}
                    className="input-field"
                  />
                </label>
              </div>

              <div className="login-credential-card">
                <span>Hazır test hesabı</span>
                <strong>{MOCK_ADMIN_EMAIL}</strong>
                <strong>{MOCK_ADMIN_PASSWORD}</strong>
              </div>

              {loginError && <div className="login-error">{loginError}</div>}

              <button type="submit" disabled={loading} className="btn btn-primary login-submit">
                {loading ? 'Admin doğrulanıyor...' : 'Admin konsolunu aç'}
              </button>
            </form>
          )}

          <p className="login-footer-copy">KVKK uyumlu · şirket içi indeksleme · rol bazlı erişim</p>
        </section>
      </div>
    </div>
  )
}

/* ── Main app ──────────────────────────────────────────── */
export default function App() {
  const [tenant, setTenant] = useState(() => loadStoredJSON('turkrag_tenant'))
  const [authSession, setAuthSession] = useState(() => loadStoredJSON(AUTH_STORAGE_KEY))
  const [tenants, setTenants] = useState([])
  const [role, setRole] = useState(() => getTokenPayload()?.role || loadStoredJSON(AUTH_STORAGE_KEY)?.role || '')
  const [tab, setTab] = useState('chat')
  const [selectedSession, setSelectedSession] = useState(null)
  const [sessionRefresh, setSessionRefresh] = useState(0)
  const [sessions, setSessions] = useState([])
  const [citations, setCitations] = useState([])
  const [attribution, setAttribution] = useState(null)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [theme, setTheme] = useState(() => localStorage.getItem('turkrag_theme') || 'light')

  const clearSessionState = () => {
    setToken('')
    setRole('')
    setAuthSession(null)
    setTenant(null)
    setTenants([])
    setSessions([])
    setCitations([])
    setSelectedSession(null)
    localStorage.removeItem('turkrag_tenant')
    localStorage.removeItem(AUTH_STORAGE_KEY)
  }

  const persistSession = (nextTenant, nextAuth) => {
    setTenant(nextTenant)
    setAuthSession(nextAuth)
    setRole(nextAuth.role)
    setTenants(nextAuth.role === 'admin' ? [] : [nextTenant])
    localStorage.setItem('turkrag_tenant', JSON.stringify(nextTenant))
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(nextAuth))
  }

  /* Apply theme to <html> */
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('turkrag_theme', theme)
  }, [theme])

  /* Validate restored token. */
  useEffect(() => {
    if (!tenant) return
    const payload = getTokenPayload()
    if (!getToken() || !payload || isTokenExpired(payload)) {
      clearSessionState()
      return
    }
    setRole(payload.role || authSession?.role || '')
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  /* Load tenant list for admins; members stay scoped to the current tenant. */
  useEffect(() => {
    if (!tenant) return
    if (role !== 'admin') {
      setTenants([tenant])
      return
    }
    api.listTenants().then(setTenants).catch(() => setTenants([tenant]))
  }, [tenant, role])

  useEffect(() => {
    if (tab === 'admin' && role !== 'admin') {
      setTab('chat')
    }
  }, [role, tab])

  /* Load session history */
  useEffect(() => {
    if (!tenant) return
    api.listSessions(30).then(setSessions).catch(() => {})
  }, [tenant, sessionRefresh])

  const handleLogout = () => {
    clearSessionState()
  }

  const handleTenantSwitch = async (t) => {
    if (!authSession) return
    try {
      const nextRole = authSession.role || 'member'
      const userId = authSession.userId || (nextRole === 'admin' ? MOCK_ADMIN_EMAIL : 'demo-user')
      const data = await api.getToken(t.id, userId, nextRole)
      setToken(data.access_token)
      setRole(getTokenPayload()?.role || nextRole)
      const nextTenant = { slug: t.slug, id: t.id, name: t.name }
      setTenant(nextTenant)
      localStorage.setItem('turkrag_tenant', JSON.stringify(nextTenant))
      setSelectedSession(null)
      setCitations([])
      setSessionRefresh((n) => n + 1)
    } catch {}
  }

  if (!tenant || !authSession || !role) {
    return (
      <ToastProvider>
        <LoginPage
          onLogin={({ tenant: nextTenant, auth: nextAuth }) => {
            persistSession(nextTenant, nextAuth)
          }}
        />
      </ToastProvider>
    )
  }

  return (
    <ToastProvider>
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>

        <Header
          tenant={tenant}
          tenants={tenants}
          role={role}
          onTenantSwitch={handleTenantSwitch}
          onLogout={handleLogout}
          theme={theme}
          onThemeToggle={() => setTheme((t) => t === 'dark' ? 'light' : 'dark')}
        />

        <div className="dashboard-body">
          <Sidebar
            tab={tab}
            onTabChange={(t) => { setTab(t); if (t !== 'chat') setCitations([]) }}
            onUploadClick={() => setTab('documents')}
            collapsed={sidebarCollapsed}
            onCollapseToggle={() => setSidebarCollapsed((v) => !v)}
            sessions={sessions}
            selectedSession={selectedSession}
            onSessionSelect={(id) => { setSelectedSession(id); setTab('chat') }}
            showAdmin={role === 'admin'}
          />

          <main className="main-stage">
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

            <div style={{
              display: tab === 'documents' ? 'block' : 'none',
              flex: 1, overflow: 'auto', padding: '20px',
            }}>
              <div className="view-pane">
                <DocumentUpload />
              </div>
            </div>

            <div style={{
              display: tab === 'analytics' ? 'block' : 'none',
              flex: 1, overflow: 'auto', padding: '20px',
            }}>
              <div className="view-pane">
                <AnalyticsDashboard />
              </div>
            </div>

            <div style={{
              display: tab === 'admin' && role === 'admin' ? 'flex' : 'none',
              flex: 1, overflow: 'auto', padding: '20px',
            }}>
              <div className="view-pane">
                <AdminPanel />
              </div>
            </div>

            {tab === 'chat' && (
              <SourcesPanel citations={citations} attribution={attribution} />
            )}
          </main>
        </div>
      </div>
    </ToastProvider>
  )
}
