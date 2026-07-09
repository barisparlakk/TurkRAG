import React, { useEffect, useState } from 'react'
import { ChatWindow } from './components/ChatWindow.jsx'
import { Header } from './components/Header.jsx'
import { Sidebar } from './components/Sidebar.jsx'
import { SourcesPanel } from './components/SourcesPanel.jsx'
import { ToastProvider } from './components/Toast.jsx'
import {
  AnalyticsPage,
  CollectionsPage,
  DashboardPage,
  DocumentsPage,
  HistoryPage,
  JobsPage,
  SettingsPage,
  SystemPage,
} from './components/OperationsPages.jsx'
import { api, getTokenPayload, getToken, setToken } from './api/client.js'

const AUTH_STORAGE_KEY = 'turkrag_auth'
const COMMANDS = [
  { id: 'dashboard', label: 'Pano', detail: 'Çalışma alanı özeti ve sağlık durumu', tab: 'dashboard' },
  { id: 'chat', label: 'Belgelere Sor', detail: 'Çalışma alanındaki belgeleri sorgula', tab: 'chat' },
  { id: 'documents', label: 'Belgeler', detail: 'Kaynakları yükle, filtrele ve yönet', tab: 'documents' },
  { id: 'collections', label: 'Koleksiyonlar', detail: 'Bilgi alanlarını düzenle', tab: 'collections' },
  { id: 'history', label: 'Geçmiş', detail: 'Kaynaklı yanıtları incele', tab: 'history' },
  { id: 'analytics', label: 'Analitik', detail: 'Kullanım, gecikme ve atıf metrikleri', tab: 'analytics' },
  { id: 'jobs', label: 'İçe Aktarım İşleri', detail: 'Ayrıştırma ve indeksleme süreçlerini izle', tab: 'jobs' },
  { id: 'settings', label: 'Ayarlar', detail: 'Pano tercihleri', tab: 'settings' },
  { id: 'system', label: 'Sistem Durumu', detail: 'Servis sağlığı ve bağlantılar', tab: 'system' },
]

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

function LoginPage({ onLogin }) {
  const [tenantSlug, setTenantSlug] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loginError, setLoginError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleLogin = async (event) => {
    event.preventDefault()
    const slug = tenantSlug.trim()
    if (!slug || !email.trim() || !password) {
      setLoginError('Çalışma alanı, e-posta ve parola zorunludur.')
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
    <main className="login-shell">
      <section className="login-card">
        <div className="login-brand-row">
          <div className="brand-mark large"><img src="/logo-dark.png" alt="" /></div>
          <div>
            <strong>TurkRAG</strong>
            <span>Yapay zekâ destekli belge zekâsı</span>
          </div>
        </div>
        <h1>Güvenli çalışma alanı erişimi</h1>
        <p>Özel kurumsal belgelerinizi kaynaklarıyla sorgulamak için giriş yapın.</p>
        <form onSubmit={handleLogin} className="login-form">
          <label>Çalışma alanı kısa adı<input value={tenantSlug} onChange={(event) => setTenantSlug(event.target.value)} placeholder="demo" /></label>
          <label>E-posta<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="baris@dev.com" /></label>
          <label>Parola<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••••" /></label>
          {loginError && <div className="inline-error">{loginError}</div>}
          <button className="primary-action wide" type="submit" disabled={loading}>{loading ? 'Doğrulanıyor…' : 'Giriş yap'}</button>
        </form>
      </section>
    </main>
  )
}

export default function App() {
  const [tenant, setTenant] = useState(() => loadStoredJSON('turkrag_tenant'))
  const [authSession, setAuthSession] = useState(() => loadStoredJSON(AUTH_STORAGE_KEY))
  const [tenants, setTenants] = useState([])
  const [role, setRole] = useState(() => getTokenPayload()?.role || loadStoredJSON(AUTH_STORAGE_KEY)?.role || '')
  const [tab, setTab] = useState('dashboard')
  const [selectedSession, setSelectedSession] = useState(null)
  const [sessionRefresh, setSessionRefresh] = useState(0)
  const [sessions, setSessions] = useState([])
  const [citations, setCitations] = useState([])
  const [attribution, setAttribution] = useState(null)
  const [hasChatMessages, setHasChatMessages] = useState(false)
  const [theme, setTheme] = useState(() => localStorage.getItem('turkrag_theme') || 'dark')
  const [health, setHealth] = useState(null)
  const [refreshTick, setRefreshTick] = useState(0)

  const clearSessionState = () => {
    setToken('')
    setRole('')
    setAuthSession(null)
    setTenant(null)
    setTenants([])
    setSessions([])
    setCitations([])
    setAttribution(null)
    setHasChatMessages(false)
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

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('turkrag_theme', theme)
  }, [theme])

  useEffect(() => {
    if (!tenant) return
    const payload = getTokenPayload()
    if (!getToken() || !payload || isTokenExpired(payload)) {
      clearSessionState()
      return
    }
    setRole(payload.role || authSession?.role || '')
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!tenant) return
    if (role !== 'platform_admin') {
      setTenants([tenant])
      return
    }
    api.listTenants().then(setTenants).catch(() => setTenants([tenant]))
  }, [tenant, role])

  useEffect(() => {
    if (!tenant) return
    api.listSessions(50).then(setSessions).catch(() => {})
  }, [tenant, sessionRefresh, refreshTick])

  useEffect(() => {
    if (!tenant) return
    api.health().then(setHealth).catch(() => setHealth(null))
  }, [tenant, refreshTick])

  const handleTenantSwitch = async (nextTenantOption) => {
    if (!authSession) return
    try {
      const nextRole = authSession.role || role || 'member'
      const userId = authSession.userId || 'demo-user'
      const data = nextRole === 'platform_admin'
        ? await api.switchAdminTenant(nextTenantOption.slug)
        : await api.getToken(nextTenantOption.id, userId)
      setToken(data.access_token)
      setRole(getTokenPayload()?.role || nextRole)
      const nextTenant = { slug: nextTenantOption.slug, id: nextTenantOption.id, name: nextTenantOption.name }
      setTenant(nextTenant)
      localStorage.setItem('turkrag_tenant', JSON.stringify(nextTenant))
      setSelectedSession(null)
      setCitations([])
      setAttribution(null)
      setHasChatMessages(false)
      setSessionRefresh((value) => value + 1)
      setTab('dashboard')
    } catch {}
  }

  if (!tenant || !authSession || !role) {
    return (
      <ToastProvider>
        <LoginPage onLogin={({ tenant: nextTenant, auth: nextAuth }) => persistSession(nextTenant, nextAuth)} />
      </ToastProvider>
    )
  }

  const navigate = (nextTab) => {
    setTab(nextTab)
    if (nextTab !== 'chat') {
      setCitations([])
      setAttribution(null)
    }
  }

  const notifications = [
    health?.status && health.status !== 'ok'
      ? {
          id: 'health',
          tone: 'warning',
          title: 'Dependency check needs attention',
          detail: `System is ${health.status}. Open System Status for details.`,
          tab: 'system',
        }
      : null,
  ].filter(Boolean)

  return (
    <ToastProvider>
      <div className="app-shell">
        <Sidebar tab={tab} onTabChange={navigate} tenant={tenant} health={health} />
        <section className="content-shell">
          <Header
            tenant={tenant}
            tenants={tenants}
            role={role}
            onTenantSwitch={handleTenantSwitch}
            onLogout={clearSessionState}
            theme={theme}
            onThemeToggle={() => setTheme((value) => value === 'dark' ? 'light' : 'dark')}
            onRefresh={() => setRefreshTick((value) => value + 1)}
            commands={COMMANDS}
            notifications={notifications}
            onCommand={(command) => navigate(command.tab)}
            onNotificationSelect={(notification) => navigate(notification.tab)}
          />
          <main className="main-stage" data-view={tab} data-chat-state={hasChatMessages ? 'active' : 'empty'}>
            {tab === 'dashboard' && <DashboardPage tenant={tenant} onNavigate={navigate} />}
            {tab === 'chat' && (
              <div className="ask-documents-view">
                <ChatWindow
                  tenant={tenant}
                  sessions={sessions}
                  selectedSession={selectedSession}
                  onSessionChange={setSelectedSession}
                  onNewSession={() => setSessionRefresh((value) => value + 1)}
                  onCitationsChange={(cits, attr) => { setCitations(cits); setAttribution(attr || null) }}
                  onMessageStateChange={setHasChatMessages}
                />
                {(citations.length > 0 || attribution?.length > 0) && (
                  <SourcesPanel citations={citations} attribution={attribution} />
                )}
              </div>
            )}
            {tab === 'documents' && <DocumentsPage onNavigate={navigate} />}
            {tab === 'collections' && <CollectionsPage />}
            {tab === 'history' && <HistoryPage />}
            {tab === 'analytics' && <AnalyticsPage />}
            {tab === 'jobs' && <JobsPage />}
            {tab === 'settings' && <SettingsPage theme={theme} onThemeChange={setTheme} />}
            {tab === 'system' && <SystemPage />}
          </main>
        </section>
      </div>
    </ToastProvider>
  )
}
