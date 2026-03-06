import { useEffect, useState } from 'react'
import AgentView from './views/agent/view'
import CustomerView from './views/customer/view'

export default function App() {
  const query = new URLSearchParams(window.location.search)
  const querySession = query.get('session')
  const storedSession = window.localStorage.getItem('fastapi_flow_session')
  const initialSession = querySession || storedSession || 'demo-session'
  const [sessionId, setSessionId] = useState(initialSession)
  const [draftSessionId, setDraftSessionId] = useState(sessionId)

  const pathname = window.location.pathname
  const isCustomer = pathname.startsWith('/customer')
  const isAgent = pathname.startsWith('/agent')

  useEffect(() => {
    window.localStorage.setItem('fastapi_flow_session', sessionId)
    const params = new URLSearchParams(window.location.search)
    if (params.get('session') !== sessionId) {
      params.set('session', sessionId)
      const queryString = params.toString()
      const nextUrl = `${window.location.pathname}${queryString ? `?${queryString}` : ''}`
      window.history.replaceState(null, '', nextUrl)
    }
  }, [sessionId])

  const applySession = () => {
    const next = draftSessionId.trim() || 'demo-session'
    setSessionId(next)
  }

  return (
    <main>
      <header className="topbar">
        <h1>FastAPI Flow</h1>
        <div className="button-row">
          <a href={`/customer?session=${encodeURIComponent(sessionId)}`}>Customer View</a>
          <a href={`/agent?session=${encodeURIComponent(sessionId)}`}>Service-Agent View</a>
        </div>
        <div className="button-row">
          <input value={draftSessionId} onChange={(e) => setDraftSessionId(e.target.value)} />
          <button onClick={applySession}>Apply Session ID</button>
        </div>
      </header>

      {!isCustomer && !isAgent && (
        <section className="panel center">
          <p>Open one tab as customer and one tab as service agent.</p>
          <p>Use the same session ID in both tabs.</p>
        </section>
      )}
      {isCustomer && <CustomerView sessionId={sessionId} />}
      {isAgent && <AgentView sessionId={sessionId} />}
    </main>
  )
}
