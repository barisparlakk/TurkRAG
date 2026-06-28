const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001'

// Axios-like wrapper for AdminPanel compatibility
export const apiClient = {
  get: async (path) => ({ data: await request('GET', path) }),
  post: async (path, body) => ({ data: await request('POST', path, body) }),
  delete: async (path) => ({ data: await request('DELETE', path) }),
}

let _token = localStorage.getItem('turkrag_token') || ''

export function setToken(token) {
  _token = token
  localStorage.setItem('turkrag_token', token)
}

export function getToken() {
  return _token
}

export function getTokenPayload() {
  if (!_token) return null
  try {
    const [, payload] = _token.split('.')
    if (!payload) return null
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/')
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')
    return JSON.parse(atob(padded))
  } catch {
    return null
  }
}

function authHeaders() {
  return _token ? { Authorization: `Bearer ${_token}` } : {}
}

async function request(method, path, body = null, isFormData = false) {
  const headers = { ...authHeaders() }
  if (body && !isFormData) headers['Content-Type'] = 'application/json'

  let res
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: isFormData ? body : body ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new Error(`API sunucusuna ulaşılamıyor (${API_BASE}). Backend çalışıyor mu?`)
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }

  if (res.status === 204) return null
  return res.json()
}

export const api = {
  // Auth
  login: (tenantSlug, email, password) =>
    request('POST', '/auth/login', { tenant_slug: tenantSlug, email, password }),
  getToken: (tenantId, userId = 'user') =>
    request('POST', '/auth/token', { tenant_id: tenantId, user_id: userId }),
  mockLogin: (tenantSlug, email, password) =>
    request('POST', '/auth/mock-login', { tenant_slug: tenantSlug, email, password }),
  switchAdminTenant: (tenantSlug) =>
    request('POST', '/auth/admin/switch-tenant', { tenant_slug: tenantSlug }),

  // Documents
  listDocuments: () => request('GET', '/documents'),
  uploadDocument: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request('POST', '/documents/upload', form, true)
  },
  deleteDocument: (docId) => request('DELETE', `/documents/${docId}`),

  // Chat (sync)
  chat: (query, topK = 5) => request('POST', '/chat', { query, top_k: topK }),

  // Tenants (admin)
  listTenants: () => request('GET', '/tenants'),
  createTenant: (name, slug) => request('POST', '/tenants', { name, slug }),
  getTenantBySlug: (slug) => request('GET', `/tenants/by-slug/${slug}`),

  // Users
  listUsers: () => request('GET', '/users'),
  createUser: (email, password, role = 'member') =>
    request('POST', '/users', { email, password, role }),
  updateUser: (userId, patch) => request('PATCH', `/users/${userId}`, patch),
  deactivateUser: (userId) => request('DELETE', `/users/${userId}`),

  // Sessions
  listSessions: (limit = 30) => request('GET', `/sessions?limit=${limit}`),
  getSessionMessages: (sessionId) => request('GET', `/sessions/${sessionId}/messages`),
  submitFeedback: (messageId, value) =>
    request('POST', `/sessions/messages/${messageId}/feedback`, { value }),

  // Analytics
  getStats: () => request('GET', '/analytics/stats'),
  getRecentQueries: (limit = 20) => request('GET', `/analytics/recent?limit=${limit}`),

  // Health
  health: () => request('GET', '/health'),

  // Export
  exportSessionTxt: (sessionId) => `${API_BASE}/export/sessions/${sessionId}/txt`,
  exportSessionJson: (sessionId) => `${API_BASE}/export/sessions/${sessionId}/json`,
  getAnalyticsReport: () => request('GET', '/export/analytics/report'),

  // Evaluation
  runEval: () => request('POST', '/eval/run'),
  getEvalHistory: () => request('GET', '/eval/history'),

  // Jobs
  listJobs: (limit = 30) => request('GET', `/documents/jobs?limit=${limit}`),
  getJobStatus: (jobId) => request('GET', `/documents/jobs/${jobId}`),

  // WebSocket URL
  wsUrl: () => `${API_BASE.replace(/^http/, 'ws')}/chat/stream`,
}
