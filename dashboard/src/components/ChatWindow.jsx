import React, { useState, useEffect, useRef } from 'react'
import { useStream } from '../hooks/useStream.js'
import { CitationPanel } from './CitationPanel.jsx'

function Message({ msg }) {
  const isUser = msg.role === 'user'
  const [showSources, setShowSources] = useState(false)

  return (
    <div style={{
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
      marginBottom: '12px',
    }}>
      <div style={{
        maxWidth: '75%',
        minWidth: '60px',
      }}>
        <div style={{
          padding: '10px 14px',
          borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
          background: isUser ? '#1a73e8' : '#fff',
          color: isUser ? '#fff' : '#1a1a1a',
          fontSize: '14px',
          lineHeight: 1.6,
          border: isUser ? 'none' : '1px solid #e0e0e0',
          boxShadow: '0 1px 3px rgba(0,0,0,0.07)',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}>
          {msg.content}
          {msg.streaming && (
            <span style={{
              display: 'inline-block',
              width: '2px',
              height: '14px',
              background: '#1a73e8',
              marginLeft: '3px',
              verticalAlign: 'text-bottom',
              animation: 'blink 1s step-end infinite',
            }} />
          )}
        </div>

        {!isUser && msg.citations && msg.citations.length > 0 && (
          <div style={{ marginTop: '4px' }}>
            <button
              onClick={() => setShowSources(!showSources)}
              style={{
                background: 'none',
                border: 'none',
                color: '#1a73e8',
                fontSize: '12px',
                cursor: 'pointer',
                padding: '2px 4px',
              }}
            >
              {showSources ? '▲ Kaynakları gizle' : `▼ ${msg.citations.length} kaynak`}
            </button>
            {showSources && (
              <div style={{ border: '1px solid #e0e0e0', borderRadius: '8px', overflow: 'hidden', marginTop: '4px' }}>
                <CitationPanel citations={msg.citations} />
              </div>
            )}
          </div>
        )}

        {msg.queryTime && (
          <div style={{ fontSize: '11px', color: '#aaa', marginTop: '3px', textAlign: 'right' }}>
            {msg.queryTime} ms
          </div>
        )}
      </div>
    </div>
  )
}

export function ChatWindow() {
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      content: 'Merhaba! Belgelerinizle ilgili sorularınızı sorabilirsiniz. Önce belge yükleyin.',
      citations: [],
    },
  ])
  const [input, setInput] = useState('')
  const { send, tokens, citations, isStreaming, error, reset } = useStream()
  const bottomRef = useRef()
  const streamMsgIdRef = useRef(null)

  // Scroll to bottom on new messages/tokens
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, tokens])

  // Update streaming message in-place
  useEffect(() => {
    if (!streamMsgIdRef.current) return
    setMessages((prev) =>
      prev.map((m) =>
        m.id === streamMsgIdRef.current
          ? { ...m, content: tokens || '…', streaming: isStreaming }
          : m
      )
    )
  }, [tokens, isStreaming])

  // When streaming finishes, attach citations
  useEffect(() => {
    if (!isStreaming && streamMsgIdRef.current && citations.length > 0) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === streamMsgIdRef.current
            ? { ...m, citations, streaming: false }
            : m
        )
      )
    }
  }, [isStreaming, citations])

  // Show error as assistant message
  useEffect(() => {
    if (error && streamMsgIdRef.current) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === streamMsgIdRef.current
            ? { ...m, content: `Hata: ${error}`, streaming: false, isError: true }
            : m
        )
      )
      streamMsgIdRef.current = null
    }
  }, [error])

  const handleSend = () => {
    const q = input.trim()
    if (!q || isStreaming) return

    const userMsgId = `u_${Date.now()}`
    const asstMsgId = `a_${Date.now()}`
    streamMsgIdRef.current = asstMsgId

    setMessages((prev) => [
      ...prev,
      { id: userMsgId, role: 'user', content: q },
      { id: asstMsgId, role: 'assistant', content: '', citations: [], streaming: true },
    ])
    setInput('')
    reset()
    send(q)
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <style>{`
        @keyframes blink { 0%, 100% { opacity: 1 } 50% { opacity: 0 } }
      `}</style>

      {/* Message list */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
      }}>
        {messages.map((msg) => <Message key={msg.id} msg={msg} />)}
        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div style={{
        borderTop: '1px solid #e0e0e0',
        padding: '12px 16px',
        display: 'flex',
        gap: '8px',
        background: '#fff',
      }}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Sorunuzu yazın… (Enter ile gönderin)"
          rows={2}
          disabled={isStreaming}
          style={{
            flex: 1,
            padding: '8px 12px',
            border: '1px solid #e0e0e0',
            borderRadius: '12px',
            fontSize: '14px',
            resize: 'none',
            outline: 'none',
            fontFamily: 'inherit',
            background: isStreaming ? '#f5f5f5' : '#fff',
            transition: 'border-color 0.15s',
          }}
          onFocus={(e) => e.target.style.borderColor = '#1a73e8'}
          onBlur={(e) => e.target.style.borderColor = '#e0e0e0'}
        />
        <button
          onClick={handleSend}
          disabled={isStreaming || !input.trim()}
          style={{
            background: isStreaming || !input.trim() ? '#cbd5e1' : '#1a73e8',
            color: '#fff',
            border: 'none',
            borderRadius: '12px',
            padding: '0 20px',
            fontSize: '14px',
            fontWeight: 600,
            cursor: isStreaming || !input.trim() ? 'not-allowed' : 'pointer',
            transition: 'background 0.15s',
            whiteSpace: 'nowrap',
          }}
        >
          {isStreaming ? '⏳' : 'Gönder'}
        </button>
      </div>
    </div>
  )
}
