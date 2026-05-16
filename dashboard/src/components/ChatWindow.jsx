import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useStream } from '../hooks/useStream.js'
import { CitationPanel } from './CitationPanel.jsx'
import { api } from '../api/client.js'

/* ── Icons ─────────────────────────────────────────────────────────────────── */
const IconSend = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
  </svg>
)
const IconUser = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
  </svg>
)
const IconBot = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="8" r="4"/><path d="M20 21a8 8 0 1 0-16 0"/>
    <line x1="12" y1="4" x2="12" y2="2"/><line x1="9.5" y1="6.5" x2="8" y2="5"/><line x1="14.5" y1="6.5" x2="16" y2="5"/>
  </svg>
)
const IconNewChat = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 5v14M5 12h14"/>
  </svg>
)
const IconCopy = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
  </svg>
)
const IconRegen = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.25"/>
  </svg>
)
const IconStop = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
    <rect x="4" y="4" width="16" height="16" rx="2"/>
  </svg>
)
const IconThumbUp = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z"/>
    <path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/>
  </svg>
)
const IconThumbDown = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z"/>
    <path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/>
  </svg>
)

function stripThink(text) {
  let out = text.replace(/<think>[\s\S]*?<\/think>/g, '')
  out = out.replace(/<think>[\s\S]*$/, '')
  return out.trimStart()
}

/* ── Action button (copy / regen / feedback) ───────────────────────────────── */
function ActionBtn({ onClick, title, active, children, color }) {
  return (
    <button
      onClick={onClick}
      title={title}
      style={{
        background: active ? (color || 'var(--accent-muted)') : 'transparent',
        border: 'none', cursor: 'pointer', padding: '3px 5px',
        borderRadius: 4, color: active ? (color ? '#fff' : 'var(--accent)') : 'var(--text-3)',
        display: 'flex', alignItems: 'center', lineHeight: 1,
        transition: 'all 0.1s',
      }}
      onMouseEnter={(e) => { if (!active) e.currentTarget.style.color = 'var(--text-2)' }}
      onMouseLeave={(e) => { if (!active) e.currentTarget.style.color = 'var(--text-3)' }}
    >
      {children}
    </button>
  )
}

/* ── Single message ────────────────────────────────────────────────────────── */
function Message({ msg, isLast, onRegenerate, isStreaming }) {
  const isUser = msg.role === 'user'
  const [showSources, setShowSources] = useState(false)
  const [copied, setCopied] = useState(false)
  const [feedback, setFeedback] = useState(msg.feedback ?? null) // 1, -1, or null

  const handleCopy = () => {
    const text = stripThink(msg.content)
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  const handleFeedback = async (value) => {
    if (!msg.message_id) return
    const next = feedback === value ? null : value
    setFeedback(next)
    try {
      if (next !== null) {
        await api.submitFeedback(msg.message_id, next)
      }
    } catch {
      setFeedback(feedback) // revert on error
    }
  }

  return (
    <div className="fade-up" style={{
      display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start',
      marginBottom: '20px', gap: '10px', alignItems: 'flex-end',
    }}>
      {/* AI avatar */}
      {!isUser && (
        <div style={{
          width: 30, height: 30, flexShrink: 0,
          background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', borderRadius: 10,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#fff', boxShadow: '0 0 12px rgba(99,102,241,0.3)',
          marginBottom: showSources && msg.citations?.length ? 0 : 2,
        }}>
          <IconBot />
        </div>
      )}

      <div style={{ maxWidth: '72%', minWidth: '60px' }}>
        {/* Bubble */}
        <div style={{
          padding: '11px 15px',
          borderRadius: isUser ? '16px 16px 4px 16px' : '4px 16px 16px 16px',
          background: isUser ? 'linear-gradient(135deg, #6366f1 0%, #7c3aed 100%)' : 'var(--surface-2)',
          color: isUser ? '#fff' : 'var(--text-1)',
          fontSize: '14px', lineHeight: 1.65,
          border: isUser ? 'none' : '1px solid var(--border)',
          boxShadow: isUser ? '0 4px 16px rgba(99,102,241,0.25)' : 'var(--shadow-sm)',
          whiteSpace: 'pre-wrap', wordBreak: 'break-word',
          minHeight: msg.streaming && !msg.content ? 38 : undefined,
        }}>
          {msg.isError
            ? <span style={{ color: 'var(--error)', fontSize: '13px' }}>{msg.content}</span>
            : stripThink(msg.content) || (msg.streaming ? null : '')}
          {!msg.isError && msg.streaming && !stripThink(msg.content) && (
            <div className="typing-dots"><span/><span/><span/></div>
          )}
          {!msg.isError && msg.streaming && stripThink(msg.content) && (
            <span style={{
              display: 'inline-block', width: 2, height: '1em',
              background: 'var(--accent)', marginLeft: 3, verticalAlign: 'text-bottom',
              animation: 'blink 0.9s step-end infinite',
            }} />
          )}
        </div>

        {/* Citations toggle */}
        {!isUser && msg.citations?.length > 0 && (
          <div style={{ marginTop: '6px' }}>
            <button
              onClick={() => setShowSources(!showSources)}
              className="btn"
              style={{
                background: showSources ? 'var(--accent-muted)' : 'transparent',
                color: 'var(--accent-hover)', fontSize: '12px', padding: '4px 10px',
                borderRadius: 20, fontWeight: 500,
                border: '1px solid ' + (showSources ? 'rgba(99,102,241,0.3)' : 'transparent'),
              }}
            >
              {showSources ? '↑ Kaynakları gizle' : `↓ ${msg.citations.length} kaynak`}
            </button>
            {showSources && (
              <div className="fade-in" style={{
                marginTop: '6px', border: '1px solid var(--border)',
                borderRadius: 'var(--radius-md)', overflow: 'hidden',
                background: 'var(--surface-1)',
              }}>
                <CitationPanel citations={msg.citations} />
              </div>
            )}
          </div>
        )}

        {/* Action bar — copy / feedback / regenerate */}
        {!isUser && !msg.streaming && !msg.isError && (
          <div style={{ display: 'flex', gap: '2px', marginTop: '6px', alignItems: 'center' }}>
            <ActionBtn onClick={handleCopy} title="Kopyala" active={copied}>
              <IconCopy />
            </ActionBtn>
            {msg.message_id && (
              <>
                <ActionBtn
                  onClick={() => handleFeedback(1)}
                  title="İyi yanıt"
                  active={feedback === 1}
                  color="#16a34a"
                >
                  <IconThumbUp />
                </ActionBtn>
                <ActionBtn
                  onClick={() => handleFeedback(-1)}
                  title="Kötü yanıt"
                  active={feedback === -1}
                  color="#dc2626"
                >
                  <IconThumbDown />
                </ActionBtn>
              </>
            )}
            {isLast && onRegenerate && !isStreaming && (
              <ActionBtn onClick={onRegenerate} title="Yeniden üret">
                <IconRegen />
              </ActionBtn>
            )}
          </div>
        )}

        {/* Query time */}
        {msg.queryTime && (
          <div style={{ fontSize: '11px', color: 'var(--text-3)', marginTop: '4px' }}>
            {(msg.queryTime / 1000).toFixed(1)}s
          </div>
        )}
      </div>

      {/* User avatar */}
      {isUser && (
        <div style={{
          width: 30, height: 30, flexShrink: 0, background: 'var(--surface-3)',
          borderRadius: 10, border: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-2)',
        }}>
          <IconUser />
        </div>
      )}
    </div>
  )
}

/* ── Empty state ───────────────────────────────────────────────────────────── */
function EmptyState() {
  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', padding: '40px 24px', gap: '16px',
    }}>
      <div style={{
        width: 64, height: 64, background: 'var(--accent-muted)',
        border: '1px solid rgba(99,102,241,0.2)', borderRadius: 20,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
      </div>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-1)', marginBottom: '6px' }}>
          Merhaba, nasıl yardımcı olabilirim?
        </div>
        <div style={{ fontSize: '13px', color: 'var(--text-2)', lineHeight: 1.6, maxWidth: 360 }}>
          Yüklediğiniz belgeler hakkında Türkçe sorular sorabilirsiniz.
          Önce <strong style={{ color: 'var(--accent-hover)' }}>Belgeler</strong> sekmesinden dosya yükleyin.
        </div>
      </div>
    </div>
  )
}

/* ── Chat window ───────────────────────────────────────────────────────────── */
export function ChatWindow({ selectedSession, onSessionChange, onNewSession }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const { send, abort, tokens, citations, queryTime, sessionId, messageId,
          isStreaming, error, reset, resetSession } = useStream()
  const bottomRef = useRef()
  const textareaRef = useRef()
  const streamMsgIdRef = useRef(null)
  const sessionIdRef = useRef(null)

  // Sync sessionIdRef ← hook state
  useEffect(() => { sessionIdRef.current = sessionId }, [sessionId])

  // Notify parent when a new session is created (for sidebar refresh)
  useEffect(() => {
    if (sessionId) onNewSession?.(sessionId)
  }, [sessionId])

  // Load a session when parent selects one from sidebar
  useEffect(() => {
    if (!selectedSession) return
    api.getSessionMessages(selectedSession).then((msgs) => {
      const loaded = msgs.map((m, i) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        citations: m.citations || [],
        feedback: m.feedback,
        message_id: m.role === 'assistant' ? m.id : undefined,
        streaming: false,
      }))
      setMessages(loaded)
      sessionIdRef.current = selectedSession
      resetSession()
      // Manually set sessionId via a dummy send won't work — use ref approach:
      // sessionIdRef is set above; next send will use it.
    }).catch(() => {})
  }, [selectedSession])

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, tokens])

  useEffect(() => {
    if (!streamMsgIdRef.current) return
    setMessages((prev) => prev.map((m) =>
      m.id === streamMsgIdRef.current ? { ...m, content: tokens || '', streaming: isStreaming } : m
    ))
  }, [tokens, isStreaming])

  useEffect(() => {
    if (!isStreaming && streamMsgIdRef.current && citations.length > 0) {
      setMessages((prev) => prev.map((m) =>
        m.id === streamMsgIdRef.current ? { ...m, citations, queryTime, streaming: false } : m
      ))
    }
  }, [isStreaming, citations, queryTime])

  // Attach message_id to the last assistant message once server sends it
  useEffect(() => {
    if (!messageId || !streamMsgIdRef.current) return
    setMessages((prev) => prev.map((m) =>
      m.id === streamMsgIdRef.current ? { ...m, message_id: messageId } : m
    ))
  }, [messageId])

  useEffect(() => {
    if (error && streamMsgIdRef.current) {
      setMessages((prev) => prev.map((m) =>
        m.id === streamMsgIdRef.current
          ? { ...m, content: `Hata: ${error}`, streaming: false, isError: true }
          : m
      ))
      streamMsgIdRef.current = null
    }
  }, [error])

  const handleSend = useCallback((queryOverride = null) => {
    const q = (queryOverride ?? input).trim()
    if (!q || isStreaming) return
    const userMsgId = `u_${Date.now()}`
    const asstMsgId = `a_${Date.now()}`
    streamMsgIdRef.current = asstMsgId
    setMessages((prev) => [
      ...prev,
      { id: userMsgId, role: 'user', content: q },
      { id: asstMsgId, role: 'assistant', content: '', citations: [], streaming: true },
    ])
    if (!queryOverride) setInput('')
    reset()
    send(q, sessionIdRef.current)
    setTimeout(() => textareaRef.current?.focus(), 0)
  }, [input, isStreaming, reset, send])

  const handleRegenerate = useCallback(() => {
    // Find last user message, strip last assistant message, resend
    const lastUser = [...messages].reverse().find((m) => m.role === 'user')
    if (!lastUser || isStreaming) return
    setMessages((prev) => {
      const lastAsstIdx = [...prev].reverse().findIndex((m) => m.role === 'assistant')
      if (lastAsstIdx === -1) return prev
      const realIdx = prev.length - 1 - lastAsstIdx
      return prev.slice(0, realIdx)
    })
    reset()
    const asstMsgId = `a_${Date.now()}`
    streamMsgIdRef.current = asstMsgId
    setMessages((prev) => [
      ...prev,
      { id: asstMsgId, role: 'assistant', content: '', citations: [], streaming: true },
    ])
    send(lastUser.content, sessionIdRef.current)
  }, [messages, isStreaming, reset, send])

  const handleNewChat = () => {
    if (isStreaming) return
    setMessages([])
    setInput('')
    reset()
    resetSession()
    sessionIdRef.current = null
    onSessionChange?.(null)
    setTimeout(() => textareaRef.current?.focus(), 0)
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const hasMessages = messages.length > 0
  const lastAsstMsg = [...messages].reverse().find((m) => m.role === 'assistant' && !m.streaming)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Top bar */}
      {hasMessages && (
        <div style={{
          flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '8px 24px', borderBottom: '1px solid var(--border)', background: 'var(--surface-1)',
        }}>
          <span style={{ fontSize: '12px', color: 'var(--text-3)' }}>
            {sessionIdRef.current ? `Oturum #${sessionIdRef.current.slice(0, 8)}` : 'Yeni sohbet'}
          </span>
          <button
            onClick={handleNewChat} disabled={isStreaming}
            className="btn"
            style={{
              display: 'flex', alignItems: 'center', gap: '5px',
              fontSize: '12px', padding: '5px 10px', color: 'var(--text-2)',
              borderRadius: 'var(--radius-md)', border: '1px solid var(--border)',
              opacity: isStreaming ? 0.4 : 1,
            }}
          >
            <IconNewChat /> Yeni Sohbet
          </button>
        </div>
      )}

      {/* Messages */}
      <div style={{
        flex: 1, overflowY: 'auto',
        padding: hasMessages ? '28px 32px' : 0,
        display: 'flex', flexDirection: 'column',
        maxWidth: 820, width: '100%', margin: '0 auto', alignSelf: 'stretch',
      }}>
        {!hasMessages ? <EmptyState /> : messages.map((msg, i) => (
          <Message
            key={msg.id} msg={msg}
            isLast={msg === lastAsstMsg}
            onRegenerate={handleRegenerate}
            isStreaming={isStreaming}
          />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div style={{
        flexShrink: 0, borderTop: '1px solid var(--border)',
        padding: '16px 24px 20px', background: 'var(--surface-1)',
      }}>
        <div style={{
          maxWidth: 820, margin: '0 auto',
          display: 'flex', gap: '10px', alignItems: 'flex-end',
          background: 'var(--surface-2)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)', padding: '10px 10px 10px 16px',
          transition: 'border-color 0.15s, box-shadow 0.15s',
        }}
          onFocusCapture={(e) => {
            e.currentTarget.style.borderColor = 'var(--accent)'
            e.currentTarget.style.boxShadow = '0 0 0 3px var(--accent-muted)'
          }}
          onBlurCapture={(e) => {
            e.currentTarget.style.borderColor = 'var(--border)'
            e.currentTarget.style.boxShadow = 'none'
          }}
        >
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Sorunuzu yazın… (Enter ile gönderin, Shift+Enter yeni satır)"
            rows={1}
            disabled={isStreaming}
            style={{
              flex: 1, resize: 'none', border: 'none', outline: 'none',
              background: 'transparent', color: 'var(--text-1)',
              fontFamily: 'var(--font)', fontSize: '14px', lineHeight: 1.6,
              maxHeight: 140, overflowY: 'auto',
            }}
            onInput={(e) => {
              e.target.style.height = 'auto'
              e.target.style.height = Math.min(e.target.scrollHeight, 140) + 'px'
            }}
          />
          <button
            onClick={isStreaming ? abort : handleSend}
            disabled={!isStreaming && !input.trim()}
            className="btn btn-primary"
            style={{ padding: '8px 14px', borderRadius: 'var(--radius-md)', flexShrink: 0, alignSelf: 'flex-end' }}
          >
            {isStreaming ? <IconStop /> : <IconSend />}
          </button>
        </div>
        <p style={{ textAlign: 'center', fontSize: '11px', color: 'var(--text-3)', marginTop: '10px' }}>
          Yanıtlar yüklenen belgeler temel alınarak üretilir
        </p>
      </div>
    </div>
  )
}
