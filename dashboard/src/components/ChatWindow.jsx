import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useStream } from '../hooks/useStream.js'
import { api } from '../api/client.js'

/* ── Icons ─────────────────────────────────────────────── */
const IconSend = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
  </svg>
)
const IconStop = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
    <rect x="4" y="4" width="16" height="16" rx="2"/>
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
const IconExport = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
    <polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
  </svg>
)
const IconPlus = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
  </svg>
)

function stripThink(text) {
  return text.replace(/<think>[\s\S]*?<\/think>/g, '').replace(/<think>[\s\S]*$/, '').trimStart()
}

/* ── Example questions chips ────────────────────────────── */
const EXAMPLE_QUESTIONS = [
  {
    label: 'İzin prosedürü nasıl işler?',
    meta: 'İK politikası',
  },
  {
    label: 'Satın alma süreci nedir?',
    meta: 'Operasyon',
  },
  {
    label: 'KVKK kapsamında verilerimi nasıl koruyabilirim?',
    meta: 'Uyum',
  },
]

function EmptyState({ onSend }) {
  return (
    <div className="chat-empty">
      <div className="chat-empty-card">
        <div className="chat-empty-orbit" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>

        <div className="chat-empty-logo">
          <img src="/logo-light.png" className="logo-light" alt="" />
          <img src="/logo-dark.png" className="logo-dark" alt="" />
        </div>

        <div className="chat-empty-copy">
          <span className="chat-eyebrow">Belge zekası hazır</span>
          <h2>Soruyu yaz, kaynaklı yanıtı al.</h2>
          <p>
            TurkRAG şirket belgelerini tenant sınırları içinde arar, yanıtı üretir
            ve dayandığı parçaları sağ panelde gösterir.
          </p>
        </div>

        <div className="chat-empty-metrics">
          <div>
            <strong>ACL</strong>
            <span>Belge yetkisi</span>
          </div>
          <div>
            <strong>RAG</strong>
            <span>Kaynaklı cevap</span>
          </div>
          <div>
            <strong>TR</strong>
            <span>Türkçe arama</span>
          </div>
        </div>
      </div>

      <div className="prompt-chips">
        {EXAMPLE_QUESTIONS.map((q, i) => (
          <button
            key={i}
            onClick={() => onSend(q.label)}
            className="prompt-chip"
          >
            <span>{q.meta}</span>
            <strong>{q.label}</strong>
          </button>
        ))}
      </div>
    </div>
  )
}

/* ── Action button ──────────────────────────────────────── */
function ActionBtn({ onClick, title, active, activeColor, children }) {
  return (
    <button
      onClick={onClick}
      title={title}
      style={{
        background: active ? (activeColor ? `${activeColor}15` : 'var(--accent-muted)') : 'transparent',
        border: 'none', cursor: 'pointer', padding: '3px 6px',
        borderRadius: 'var(--radius-sm)',
        color: active ? (activeColor || 'var(--accent)') : 'var(--text-3)',
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

/* ── Single message bubble ──────────────────────────────── */
function Message({ msg, isLast, onRegenerate, onFollowUp, isStreaming }) {
  const isUser = msg.role === 'user'
  const [copied, setCopied] = useState(false)
  const [feedback, setFeedback] = useState(msg.feedback ?? null)

  const content = stripThink(msg.content)
  const ts = msg.created_at
    ? new Date(msg.created_at).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })
    : null

  const handleCopy = () => {
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  const handleFeedback = async (value) => {
    if (!msg.message_id) return
    const next = feedback === value ? null : value
    setFeedback(next)
    try {
      if (next !== null) await api.submitFeedback(msg.message_id, next)
    } catch { setFeedback(feedback) }
  }

  return (
    <div className={`message-row fade-up ${isUser ? 'user' : 'assistant'}`} style={{
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
      marginBottom: '20px',
      gap: '10px',
    }}>
      {/* Avatar — assistant only; user has no avatar */}
      {!isUser && (
        <div className="message-avatar">
          <img src="/logo-light.png" className="logo-light" alt="" />
          <img src="/logo-dark.png" className="logo-dark" alt="" />
        </div>
      )}

      <div style={{ maxWidth: '72%', minWidth: 60 }}>
        <div className={`message-bubble ${isUser ? 'user' : 'assistant'}`} style={{
          minHeight: msg.streaming && !content ? 38 : undefined,
        }}>
          {msg.isError
            ? <span style={{ color: 'var(--error)', fontSize: '13px' }}>{msg.content}</span>
            : content || (msg.streaming
                ? <div className="typing-dots"><span/><span/><span/></div>
                : ''
              )
          }
          {!msg.isError && msg.streaming && content && (
            <span className="stream-cursor" />
          )}
        </div>

        <div className={`message-meta ${isUser ? 'right' : ''}`}>
          {ts && <span style={{ fontSize: '11px', color: 'var(--text-3)' }}>{ts}</span>}
          {!isUser && msg.streaming && (
            <span style={{ fontSize: '11px', color: 'var(--text-3)' }}>⏱ {msg.elapsed ?? 0}s…</span>
          )}
          {!isUser && !msg.streaming && msg.queryTime && (
            <span style={{ fontSize: '11px', color: 'var(--text-3)' }}>
              {(msg.queryTime / 1000).toFixed(1)}s
            </span>
          )}
        </div>

        {!isUser && !msg.streaming && !msg.isError && (
          <div style={{ display: 'flex', gap: '2px', marginTop: '4px' }}>
            <ActionBtn onClick={handleCopy} title={copied ? 'Kopyalandı' : 'Kopyala'} active={copied}>
              <IconCopy />
            </ActionBtn>
            {msg.message_id && (
              <>
                <ActionBtn onClick={() => handleFeedback(1)} title="İyi yanıt" active={feedback === 1} activeColor="#059669">
                  <IconThumbUp />
                </ActionBtn>
                <ActionBtn onClick={() => handleFeedback(-1)} title="Kötü yanıt" active={feedback === -1} activeColor="#dc2626">
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

        {!isUser && isLast && msg.followUps?.length > 0 && !msg.streaming && (
          <div className="followup-list">
            {msg.followUps.map((q, i) => (
              <button
                key={i}
                onClick={() => onFollowUp?.(q)}
                className="followup-chip"
              >
                {q}
              </button>
            ))}
          </div>
        )}
      </div>

    </div>
  )
}

/* ── Main chat window ───────────────────────────────────── */
export function ChatWindow({ selectedSession, onSessionChange, onNewSession, onCitationsChange }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [elapsed, setElapsed] = useState(0)

  const { send, abort, tokens, citations, attribution, queryTime, sessionId, messageId,
          followUps, isStreaming, error, reset, resetSession } = useStream()

  const bottomRef = useRef()
  const textareaRef = useRef()
  const streamMsgIdRef = useRef(null)
  const sessionIdRef = useRef(null)
  const streamStartRef = useRef(null)

  // Elapsed timer
  useEffect(() => {
    if (isStreaming) {
      streamStartRef.current = Date.now()
      setElapsed(0)
      const id = setInterval(() => {
        setElapsed(((Date.now() - streamStartRef.current) / 1000).toFixed(1))
      }, 100)
      return () => clearInterval(id)
    }
  }, [isStreaming])

  useEffect(() => { sessionIdRef.current = sessionId }, [sessionId])
  useEffect(() => { if (sessionId) onNewSession?.(sessionId) }, [sessionId])

  // Load session from sidebar
  useEffect(() => {
    if (!selectedSession) return
    api.getSessionMessages(selectedSession).then((msgs) => {
      setMessages(msgs.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        citations: m.citations || [],
        feedback: m.feedback,
        message_id: m.role === 'assistant' ? m.id : undefined,
        streaming: false,
        created_at: m.created_at,
      })))
      sessionIdRef.current = selectedSession
      resetSession()
      // Show last assistant citations in sources panel
      const lastAsst = [...msgs].reverse().find((m) => m.role === 'assistant')
      if (lastAsst) onCitationsChange?.(lastAsst.citations || [])
    }).catch(() => {})
  }, [selectedSession])

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, tokens])

  // Update streaming message
  useEffect(() => {
    if (!streamMsgIdRef.current) return
    setMessages((prev) => prev.map((m) =>
      m.id === streamMsgIdRef.current
        ? { ...m, content: tokens || '', streaming: isStreaming, elapsed }
        : m
    ))
  }, [tokens, isStreaming, elapsed])

  // Attach citations + queryTime when done
  useEffect(() => {
    if (!isStreaming && streamMsgIdRef.current && citations.length > 0) {
      setMessages((prev) => prev.map((m) =>
        m.id === streamMsgIdRef.current
          ? { ...m, citations, queryTime, streaming: false }
          : m
      ))
      onCitationsChange?.(citations)
    }
  }, [isStreaming, citations, queryTime])

  // Attach attribution sentences when received
  useEffect(() => {
    if (!attribution || !streamMsgIdRef.current) return
    setMessages((prev) => prev.map((m) =>
      m.id === streamMsgIdRef.current ? { ...m, attribution } : m
    ))
    onCitationsChange?.(messages.find((m) => m.id === streamMsgIdRef.current)?.citations || citations, attribution)
  }, [attribution])

  // Attach message_id
  useEffect(() => {
    if (!messageId || !streamMsgIdRef.current) return
    setMessages((prev) => prev.map((m) =>
      m.id === streamMsgIdRef.current ? { ...m, message_id: messageId } : m
    ))
  }, [messageId])

  // Attach follow-ups
  useEffect(() => {
    if (!followUps.length || !streamMsgIdRef.current) return
    setMessages((prev) => prev.map((m) =>
      m.id === streamMsgIdRef.current ? { ...m, followUps } : m
    ))
  }, [followUps])

  // Error
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
    onCitationsChange?.([]) // clear sources panel
    setMessages((prev) => [
      ...prev,
      { id: userMsgId, role: 'user', content: q, created_at: new Date().toISOString() },
      { id: asstMsgId, role: 'assistant', content: '', citations: [], streaming: true },
    ])
    if (!queryOverride) setInput('')
    reset()
    send(q, sessionIdRef.current)
    setTimeout(() => textareaRef.current?.focus(), 0)
  }, [input, isStreaming, reset, send])

  const handleRegenerate = useCallback(() => {
    const lastUser = [...messages].reverse().find((m) => m.role === 'user')
    if (!lastUser || isStreaming) return
    setMessages((prev) => {
      const idx = [...prev].reverse().findIndex((m) => m.role === 'assistant')
      return idx === -1 ? prev : prev.slice(0, prev.length - 1 - idx)
    })
    reset()
    const asstMsgId = `a_${Date.now()}`
    streamMsgIdRef.current = asstMsgId
    onCitationsChange?.([])
    setMessages((prev) => [...prev, { id: asstMsgId, role: 'assistant', content: '', citations: [], streaming: true }])
    send(lastUser.content, sessionIdRef.current)
  }, [messages, isStreaming, reset, send])

  const handleExport = useCallback(() => {
    const lines = messages.map((m) => {
      const role = m.role === 'user' ? '**Kullanıcı**' : '**Asistan**'
      const content = stripThink(m.content)
      const cits = m.citations?.length ? '\n\n*Kaynaklar: ' + m.citations.map((c) => c.filename).join(', ') + '*' : ''
      return `${role}\n\n${content}${cits}`
    })
    const md = `# TurkRAG Sohbet Geçmişi\n\n${lines.join('\n\n---\n\n')}`
    const blob = new Blob([md], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `sohbet-${new Date().toISOString().slice(0, 10)}.md`
    a.click()
    URL.revokeObjectURL(url)
  }, [messages])

  const handleNewChat = useCallback(() => {
    if (isStreaming) return
    setMessages([]); setInput('')
    reset(); resetSession()
    sessionIdRef.current = null
    onSessionChange?.(null)
    onCitationsChange?.([])
    setTimeout(() => textareaRef.current?.focus(), 0)
  }, [isStreaming, reset, resetSession])

  const handleFollowUp = useCallback((q) => { if (!isStreaming) handleSend(q) }, [isStreaming, handleSend])

  const handleKey = (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); handleSend() }
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const hasMessages = messages.length > 0
  const lastAsstMsg = [...messages].reverse().find((m) => m.role === 'assistant' && !m.streaming)

  return (
    <div className="chat-shell">
      {hasMessages && (
        <div className="chat-topbar">
          <span>
            {sessionIdRef.current ? `Oturum #${sessionIdRef.current.slice(0, 8)}` : 'Yeni sohbet'}
          </span>
          <div style={{ display: 'flex', gap: '6px' }}>
            <button
              onClick={handleExport}
              disabled={!messages.length}
              className="btn btn-ghost"
              title="Markdown olarak indir"
            >
              <IconExport /> İndir
            </button>
            <button
              onClick={handleNewChat}
              disabled={isStreaming}
              className="btn btn-ghost"
            >
              <IconPlus /> Yeni
            </button>
          </div>
        </div>
      )}

      <div className={`message-list ${hasMessages ? 'has-messages' : ''}`}>
        {!hasMessages
          ? <EmptyState onSend={handleSend} />
          : messages.map((msg) => (
            <Message
              key={msg.id}
              msg={msg}
              isLast={msg === lastAsstMsg}
              onRegenerate={handleRegenerate}
              onFollowUp={handleFollowUp}
              isStreaming={isStreaming}
            />
          ))
        }
        <div ref={bottomRef} />
      </div>

      <div className="composer-shell">
        <div className="composer"
          onFocusCapture={(e) => {
            e.currentTarget.style.borderColor = 'var(--accent)'
            e.currentTarget.style.boxShadow = '0 0 0 2px var(--accent-muted)'
          }}
          onBlurCapture={(e) => {
            e.currentTarget.style.borderColor = 'var(--border)'
            e.currentTarget.style.boxShadow = 'none'
          }}
        >
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => {
              setInput(e.target.value)
              e.target.style.height = 'auto'
              e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
            }}
            onKeyDown={handleKey}
            placeholder="Sorunuzu yazın… (Enter ile gönderin)"
            rows={1}
            disabled={isStreaming}
            style={{
              flex: 1, resize: 'none', border: 'none', outline: 'none',
              boxShadow: 'var(--shadow-xs)',
              background: 'transparent', color: 'var(--text-1)',
              fontFamily: 'var(--font)', fontSize: '14px', lineHeight: 1.6,
              maxHeight: 120, overflowY: 'auto',
            }}
          />
          <button
            onClick={isStreaming ? abort : () => handleSend()}
            disabled={!isStreaming && !input.trim()}
            className="btn btn-primary"
            style={{ padding: '7px 12px', flexShrink: 0, alignSelf: 'flex-end' }}
          >
            {isStreaming ? <IconStop /> : <IconSend />}
          </button>
        </div>
      </div>
    </div>
  )
}
