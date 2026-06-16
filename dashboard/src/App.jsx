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
  const [tenantSlug, setTenantSlug] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loginError, setLoginError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleLogin = async (e) => {
    e.preventDefault()
    const slug = tenantSlug.trim()
    if (!slug || !email.trim() || !password) {
      setLoginError('Çalışma alanı, email ve şifre zorunludur.')
      return
    }

    setLoading(true)
    setLoginError('')
    try {
      const data = await api.login(slug, email.trim(), password)
      setToken(data.access_token)
      onLogin({
        tenant: {
          slug: data.tenant.slug,
          id: data.tenant.id,
          name: data.tenant.name || data.tenant.slug,
        },
        auth: {
          loginMode: 'password',
          role: data.user.role,
          userId: data.user.id,
          email: data.user.email,
        },
      })
    } catch (err) {
      setLoginError(`Giriş başarısız: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-shell">
      <div className="login-stage fade-up">
        <section className="login-hero glass">
          <div className="login-badge">TurkRAG access control</div>
          <h1>Kurumsal belgeler için güvenli tenant girişi</h1>
          <p>
            Kullanıcılar tenant, email ve şifre ile doğrulanır; admin araçları yalnızca
            yetkili hesaplara açılır.
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
            <div className="login-admin-note-label">Güvenli oturum</div>
            <code>tenant scoped</code>
            <code>role aware</code>
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

            <form onSubmit={handleLogin} className="login-form">
              <div className="login-form-copy">
                <h3>Çalışma alanına giriş yap</h3>
                <p>Hesabınızın rolüne göre sohbet, belge ve yönetim panelleri açılır.</p>
              </div>

              <label className="login-label">
                Çalışma alanı slug
                <input
                  type="text"
                  value={tenantSlug}
                  onChange={(e) => setTenantSlug(e.target.value)}
                  placeholder="ornek: acme-sirket"
                  className="input-field"
                />
              </label>

              <div className="login-grid-two">
                <label className="login-label">
                  Email
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="admin@acme.com"
                    className="input-field"
                  />
                </label>
                <label className="login-label">
                  Şifre
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="input-field"
                  />
                </label>
              </div>

              {loginError && <div className="login-error">{loginError}</div>}

              <button type="submit" disabled={loading} className="btn btn-primary login-submit">
                {loading ? 'Oturum doğrulanıyor...' : 'Giriş yap'}
              </button>
            </form>

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
      const userId = authSession.userId || 'demo-user'
      const data = nextRole === 'admin'
        ? await api.switchAdminTenant(t.slug)
        : await api.getToken(t.id, userId)
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

        <div
          className="dashboard-body"
          data-view={tab}
          onPointerMove={(event) => {
            const rect = event.currentTarget.getBoundingClientRect()
            const x = ((event.clientX - rect.left) / rect.width) * 100
            const y = ((event.clientY - rect.top) / rect.height) * 100
            event.currentTarget.style.setProperty('--pointer-x', `${x.toFixed(2)}%`)
            event.currentTarget.style.setProperty('--pointer-y', `${y.toFixed(2)}%`)
          }}
          onPointerLeave={(event) => {
            event.currentTarget.style.setProperty('--pointer-x', '50%')
            event.currentTarget.style.setProperty('--pointer-y', '45%')
          }}
        >
          <div className="ambient-scene" aria-hidden="true">
            <span className="ambient-field ambient-field-a" />
            <span className="ambient-field ambient-field-b" />
            <span className="ambient-field ambient-field-c" />
          </div>

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
