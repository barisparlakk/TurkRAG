import React, { createContext, useContext, useState, useCallback, useRef } from 'react'

const ToastCtx = createContext(null)

export function useToast() {
  return useContext(ToastCtx)
}

let _nextId = 1

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const timers = useRef({})

  const dismiss = useCallback((id) => {
    clearTimeout(timers.current[id])
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const toast = useCallback((message, type = 'info', duration = 3000) => {
    const id = _nextId++
    setToasts((prev) => [...prev, { id, message, type }])
    timers.current[id] = setTimeout(() => dismiss(id), duration)
    return id
  }, [dismiss])

  const success = useCallback((msg, d) => toast(msg, 'success', d), [toast])
  const error   = useCallback((msg, d) => toast(msg, 'error',   d ?? 5000), [toast])
  const info    = useCallback((msg, d) => toast(msg, 'info',    d), [toast])

  return (
    <ToastCtx.Provider value={{ toast, success, error, info, dismiss }}>
      {children}
      {/* Toast container */}
      <div style={{
        position: 'fixed', bottom: 20, right: 20, zIndex: 9999,
        display: 'flex', flexDirection: 'column', gap: '8px',
        pointerEvents: 'none',
      }}>
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

function ToastItem({ toast: t, onDismiss }) {
  const colors = {
    success: { bg: 'var(--success-muted)', border: 'var(--success)', color: 'var(--success)' },
    error:   { bg: 'var(--error-muted)',   border: 'var(--error)',   color: 'var(--error)'   },
    info:    { bg: 'var(--surface-1)',     border: 'var(--border)',  color: 'var(--text-1)'  },
  }
  const c = colors[t.type] || colors.info
  const icon = { success: '✓', error: '✕', info: 'ℹ' }[t.type]

  return (
    <button
      type="button"
      onClick={onDismiss}
      aria-label="Bildirimi kapat"
      style={{
        pointerEvents: 'all',
        background: c.bg,
        border: `1px solid ${c.border}`,
        borderRadius: 'var(--radius-lg)',
        padding: '10px 14px',
        display: 'flex', alignItems: 'center', gap: '10px',
        minWidth: 240, maxWidth: 360,
        cursor: 'pointer', textAlign: 'left',
        animation: 'toastIn 0.18s ease both',
        boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
      }}
    >
      <span style={{ color: c.color, fontWeight: 700, flexShrink: 0 }}>{icon}</span>
      <span style={{ fontSize: '13px', color: 'var(--text-1)', flex: 1 }}>{t.message}</span>
    </button>
  )
}
