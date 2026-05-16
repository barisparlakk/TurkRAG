import { useState, useCallback, useRef } from 'react'
import { api, getToken } from '../api/client.js'

/**
 * WebSocket streaming hook for TurkRAG chat.
 * Returns { send, tokens, citations, queryTime, sessionId, isStreaming, error, reset }
 *
 * Pass a sessionId to continue an existing conversation; omit (or pass null)
 * to start a new one. The hook updates sessionId from the server's 'done' frame.
 */
export function useStream() {
  const [tokens, setTokens] = useState('')
  const [citations, setCitations] = useState([])
  const [queryTime, setQueryTime] = useState(null)
  const [sessionId, setSessionId] = useState(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState(null)
  const wsRef = useRef(null)

  const reset = useCallback(() => {
    setTokens('')
    setCitations([])
    setQueryTime(null)
    setError(null)
    setIsStreaming(false)
  }, [])

  const resetSession = useCallback(() => {
    setSessionId(null)
  }, [])

  const send = useCallback((query, currentSessionId = null, topK = 5) => {
    // Close any existing connection
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    reset()
    setIsStreaming(true)

    const ws = new WebSocket(api.wsUrl())
    wsRef.current = ws

    ws.onopen = () => {
      ws.send(JSON.stringify({
        query,
        top_k: topK,
        token: getToken(),
        session_id: currentSessionId,
      }))
    }

    ws.onmessage = (event) => {
      let frame
      try {
        frame = JSON.parse(event.data)
      } catch {
        return
      }

      if (frame.type === 'token') {
        setTokens((prev) => prev + frame.content)
      } else if (frame.type === 'done') {
        setCitations(frame.citations || [])
        setQueryTime(frame.query_time_ms ?? null)
        if (frame.session_id) setSessionId(frame.session_id)
        setIsStreaming(false)
        ws.close()
      } else if (frame.type === 'error') {
        setError(frame.message)
        setIsStreaming(false)
        ws.close()
      }
    }

    ws.onerror = () => {
      setError('WebSocket bağlantı hatası')
      setIsStreaming(false)
    }

    ws.onclose = () => {
      setIsStreaming(false)
    }
  }, [reset])

  return { send, tokens, citations, queryTime, sessionId, isStreaming, error, reset, resetSession }
}
