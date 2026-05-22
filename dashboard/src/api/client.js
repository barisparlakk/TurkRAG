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

function authHeaders() {
  return _token ? { Authorization: `Bearer ${_token}` } : {}
}

async function request(method, path, body = null, isFormData = false) {
  const headers = { ...authHeaders() }
  if (body && !isFormData) headers['Content-Type'] = 'application/json'

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: isFormData ? body : body ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }

  if (res.status === 204) return null
  return res.json()
}

export const api = {
  // Auth
  getToken: (tenantId, userId = 'user', role = 'member') =>
    request('POST', '/auth/token', { tenant_id: tenantId, user_id: userId, role }),

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
  getJobStatus: (jobId) => request('GET', `/jobs/${jobId}`),

  // WebSocket URL
  wsUrl: () => `${API_BASE.replace(/^http/, 'ws')}/chat/stream`,
}
