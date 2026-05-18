import { useState, useCallback, useRef, useEffect } from 'react'
import { api, getToken } from '../api/client.js'

/**
 * WebSocket streaming hook for TurkRAG chat.
 * Returns { send, abort, tokens, citations, queryTime, sessionId, messageId,
 *           followUps, isStreaming, error, reset, resetSession }
 *
 * - Pass sessionId to continue an existing conversation.
 * - messageId is set after the server sends the message_id frame (post-save).
 * - followUps is set after the server sends the follow_ups frame.
 * - abort() cancels an in-flight stream.
 */
export function useStream() {
  const [tokens, setTokens] = useState('')
  const [citations, setCitations] = useState([])
  const [queryTime, setQueryTime] = useState(null)
  const [sessionId, setSessionId] = useState(null)
  const [messageId, setMessageId] = useState(null)
  const [followUps, setFollowUps] = useState([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState(null)
  const wsRef = useRef(null)

  useEffect(() => {
    return () => { wsRef.current?.close(); wsRef.current = null }
  }, [])

  const reset = useCallback(() => {
    setTokens('')
    setCitations([])
    setQueryTime(null)
    setMessageId(null)
    setFollowUps([])
    setError(null)
    setIsStreaming(false)
  }, [])

  const resetSession = useCallback(() => setSessionId(null), [])

  const abort = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setIsStreaming(false)
  }, [])

  const send = useCallback((query, currentSessionId = null, topK = 5) => {
    wsRef.current?.close()
    wsRef.current = null

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
      try { frame = JSON.parse(event.data) } catch { return }

      if (frame.type === 'token') {
        setTokens((prev) => prev + frame.content)
      } else if (frame.type === 'done') {
        setCitations(frame.citations || [])
        setQueryTime(frame.query_time_ms ?? null)
        if (frame.session_id) setSessionId(frame.session_id)
        setIsStreaming(false)
        // Don't close yet — follow_ups and message_id frames still coming
      } else if (frame.type === 'follow_ups') {
        if (frame.questions?.length) setFollowUps(frame.questions)
        // Don't close yet — message_id frame still coming
      } else if (frame.type === 'message_id') {
        if (frame.message_id) setMessageId(frame.message_id)
        ws.close() // message_id is last server frame — safe to close
      } else if (frame.type === 'error') {
        setError(frame.message)
        setIsStreaming(false)
        ws.close()
      }
    }

    ws.onerror = () => { setError('WebSocket bağlantı hatası'); setIsStreaming(false) }
    ws.onclose = () => { setIsStreaming(false) }
  }, [reset])

  return { send, abort, tokens, citations, queryTime, sessionId, messageId,
           followUps, isStreaming, error, reset, resetSession }
}
