import { useEffect, useMemo, useRef, useState } from 'react'

const WS_URL = 'ws://localhost:8000/ws/chat'

export default function App() {
  const [username, setUsername] = useState('')
  const [draftName, setDraftName] = useState('')
  const [message, setMessage] = useState('')
  const [messages, setMessages] = useState([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const messagesEndRef = useRef(null)

  const canSend = useMemo(
    () => connected && username.trim().length > 0 && message.trim().length > 0,
    [connected, username, message]
  )

  useEffect(() => {
    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
    }

    ws.onmessage = (event) => {
      setMessages((prev) => [...prev, event.data])
    }

    ws.onclose = () => {
      setConnected(false)
    }

    return () => {
      ws.close()
    }
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSetName = (e) => {
    e.preventDefault()
    setUsername(draftName.trim())
  }

  const handleSend = (e) => {
    e.preventDefault()
    if (!canSend) return

    const payload = `${username}: ${message.trim()}`
    wsRef.current.send(payload)
    setMessage('')
  }

  return (
    <main className="app-shell">
      <section className="chat-card">
        <h1>Realtime Chat</h1>

        <form className="name-form" onSubmit={handleSetName}>
          <input
            value={draftName}
            onChange={(e) => setDraftName(e.target.value)}
            placeholder="Set your name"
          />
          <button type="submit">Save name</button>
        </form>

        <p className={connected ? 'status ok' : 'status offline'}>
          {connected ? 'Connected to server' : 'Disconnected'}
        </p>

        <div className="messages">
          {messages.map((item, idx) => (
            <div key={`${item}-${idx}`} className="message-item">
              {item}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        <form className="send-form" onSubmit={handleSend}>
          <input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder={username ? 'Type message...' : 'Set name first...'}
          />
          <button type="submit" disabled={!canSend}>
            Send
          </button>
        </form>
      </section>
    </main>
  )
}
