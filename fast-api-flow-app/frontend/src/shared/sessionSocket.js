import { useEffect, useRef, useState } from 'react'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

function wsUrl(path) {
  const base = BACKEND_URL.replace('http://', 'ws://').replace('https://', 'wss://')
  return `${base}${path}`
}

function resolveSessionId(preferredSessionId) {
  const query = new URLSearchParams(window.location.search)
  const fromUrl = (query.get('session') || '').trim()
  if (fromUrl) return fromUrl

  const fromStorage = (window.localStorage.getItem('fastapi_flow_session') || '').trim()
  if (fromStorage) return fromStorage

  return (preferredSessionId || '').trim()
}

export function useSessionSocket(role, sessionId) {
  const socketRef = useRef(null)
  const [connected, setConnected] = useState(false)
  const [messages, setMessages] = useState([])

  useEffect(() => {
    const effectiveSessionId = resolveSessionId(sessionId)
    if (!effectiveSessionId) return

    const socket = new WebSocket(wsUrl(`/ws/${role}/${effectiveSessionId}`))
    socketRef.current = socket

    socket.onopen = () => setConnected(true)
    socket.onclose = () => setConnected(false)
    socket.onerror = () => setConnected(false)
    socket.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data)
        setMessages((prev) => [...prev, data])
      } catch {
        // Ignore malformed messages.
      }
    }

    return () => {
      socket.onmessage = null
      socket.onerror = null
      socket.onclose = null
      if (socket.readyState === WebSocket.CONNECTING) {
        socket.addEventListener(
          'open',
          () => {
            socket.close()
          },
          { once: true },
        )
        return
      }
      socket.close()
    }
  }, [role, sessionId])

  const send = (payload) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(payload))
    }
  }

  return { connected, messages, send }
}
