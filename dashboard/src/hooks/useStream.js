import { useState, useCallback, useRef } from 'react'
import { api, getToken } from '../api/client.js'

/**
 * WebSocket streaming hook for TurkRAG chat.
 * Returns { send, tokens, citations, isStreaming, error, reset }
 */
export function useStream() {
  const [tokens, setTokens] = useState('')
  const [citations, setCitations] = useState([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState(null)
  const wsRef = useRef(null)

  const reset = useCallback(() => {
    setTokens('')
    setCitations([])
    setError(null)
    setIsStreaming(false)
  }, [])

  const send = useCallback((query, topK = 5) => {
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
      ws.send(JSON.stringify({ query, top_k: topK, token: getToken() }))
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

  return { send, tokens, citations, isStreaming, error, reset }
}
