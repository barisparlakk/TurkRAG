import React, { useState, useEffect } from 'react'
import { ChatWindow } from './components/ChatWindow.jsx'
import { DocumentUpload } from './components/DocumentUpload.jsx'
import { TenantBadge } from './components/TenantBadge.jsx'
import { api, setToken, getToken } from './api/client.js'

export default function App() {
  const [tab, setTab] = useState('chat')
  const [tenantSlug, setTenantSlug] = useState('')
  const [tenantId, setTenantId] = useState('')
  const [loginSlug, setLoginSlug] = useState('')
  const [loginError, setLoginError] = useState('')
  const [tenants, setTenants] = useState([])
  const [loadingTenants, setLoadingTenants] = useState(false)

  // Load tenant list from API for the login picker
  useEffect(() => {
    setLoadingTenants(true)
    // Use an admin token from localStorage if available, else try without auth
    api.listTenants()
      .then(setTenants)
      .catch(() => setTenants([]))
      .finally(() => setLoadingTenants(false))
  }, [])

  const handleLogin = async (e) => {
    e.preventDefault()
    setLoginError('')
    const slug = loginSlug.trim()
    if (!slug) {
      setLoginError('Lütfen bir çalışma alanı slug giriniz')
      return
    }

    try {
      // Resolve slug → UUID via public endpoint, then issue a JWT
      const tenant = await api.getTenantBySlug(slug)
      const data = await api.getToken(tenant.id, 'demo-user', 'member')
      setToken(data.access_token)
      setTenantId(tenant.id)
      setTenantSlug(slug)
    } catch (err) {
      setLoginError(`Giriş başarısız: ${err.message}`)
    }
  }

  // Show login screen if no tenant selected
  if (!tenantSlug) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #e8f4fd 0%, #f5f5f5 100%)',
      }}>
        <div style={{
          background: '#fff',
          borderRadius: '16px',
          padding: '40px 36px',
          boxShadow: '0 4px 24px rgba(0,0,0,0.10)',
          width: '360px',
          maxWidth: '90vw',
        }}>
          <div style={{ textAlign: 'center', marginBottom: '28px' }}>
            <div style={{ fontSize: '36px', marginBottom: '8px' }}>🇹🇷</div>
            <h1 style={{ fontSize: '24px', fontWeight: 700, color: '#1a1a1a' }}>TurkRAG</h1>
            <p style={{ fontSize: '13px', color: '#888', marginTop: '4px' }}>
              Türkçe Kurumsal Belge Asistanı
            </p>
          </div>

          <form onSubmit={handleLogin}>
            <label style={{ fontSize: '13px', color: '#555', fontWeight: 500 }}>
              Çalışma Alanı
            </label>
            {tenants.length > 0 ? (
              <select
                value={loginSlug}
                onChange={(e) => setLoginSlug(e.target.value)}
                style={{
                  display: 'block',
                  width: '100%',
                  padding: '10px 12px',
                  marginTop: '6px',
                  marginBottom: '16px',
                  border: '1px solid #e0e0e0',
                  borderRadius: '8px',
                  fontSize: '14px',
                  outline: 'none',
                }}
              >
                <option value="">— Seçiniz —</option>
                {tenants.map((t) => (
                  <option key={t.id} value={t.slug}>{t.name} ({t.slug})</option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                value={loginSlug}
                onChange={(e) => setLoginSlug(e.target.value)}
                placeholder="ornek: acme-sirket"
                style={{
                  display: 'block',
                  width: '100%',
                  padding: '10px 12px',
                  marginTop: '6px',
                  marginBottom: '16px',
                  border: '1px solid #e0e0e0',
                  borderRadius: '8px',
                  fontSize: '14px',
                  outline: 'none',
                }}
              />
            )}

            {loginError && (
              <div style={{ color: '#b91c1c', fontSize: '13px', marginBottom: '12px', padding: '8px', background: '#fde8e8', borderRadius: '6px' }}>
                {loginError}
              </div>
            )}

            <button
              type="submit"
              style={{
                width: '100%',
                padding: '11px',
                background: '#1a73e8',
                color: '#fff',
                border: 'none',
                borderRadius: '8px',
                fontSize: '15px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Giriş Yap
            </button>
          </form>
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#f5f5f5' }}>
      {/* Header */}
      <div style={{
        background: '#fff',
        borderBottom: '1px solid #e0e0e0',
        padding: '10px 20px',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
      }}>
        <span style={{ fontSize: '20px' }}>🇹🇷</span>
        <span style={{ fontWeight: 700, fontSize: '17px', color: '#1a1a1a' }}>TurkRAG</span>
        <TenantBadge tenantSlug={tenantSlug} />
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '4px' }}>
          {['chat', 'documents'].map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={{
                padding: '6px 16px',
                border: 'none',
                borderRadius: '20px',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: 600,
                background: tab === t ? '#1a73e8' : 'transparent',
                color: tab === t ? '#fff' : '#555',
                transition: 'all 0.15s',
              }}
            >
              {t === 'chat' ? '💬 Sohbet' : '📂 Belgeler'}
            </button>
          ))}
          <button
            onClick={() => { setToken(''); setTenantSlug(''); setTenantId('') }}
            style={{ padding: '6px 12px', border: 'none', borderRadius: '20px', cursor: 'pointer', fontSize: '13px', color: '#888', background: 'transparent' }}
          >
            Çıkış
          </button>
        </div>
      </div>

      {/* Main content */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {tab === 'chat' ? (
          <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', maxWidth: '860px', width: '100%', margin: '0 auto', background: '#fff', boxShadow: '0 0 0 1px #e0e0e0' }}>
            <ChatWindow />
          </div>
        ) : (
          <div style={{ flex: 1, overflow: 'auto', maxWidth: '700px', width: '100%', margin: '0 auto' }}>
            <DocumentUpload />
          </div>
        )}
      </div>
    </div>
  )
}
