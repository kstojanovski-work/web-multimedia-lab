import { useEffect, useMemo, useRef, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

function App() {
  const [text, setText] = useState('Guten Tag, wie kann ich Ihnen helfen?')
  const [mode, setMode] = useState('gloss')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [job, setJob] = useState(null)
  const [error, setError] = useState('')

  const pollRef = useRef(null)
  const wsRef = useRef(null)

  const wsTranslateUrl = useMemo(() => API_BASE.replace('http', 'ws') + '/ws/translate', [])
  const wsJobUrl = useMemo(() => {
    if (!job?.job_id) return null
    return API_BASE.replace('http', 'ws') + `/ws/jobs/${job.job_id}`
  }, [job])

  const resolvedVideoUrl = useMemo(() => {
    if (!result?.video_url) return null
    return new URL(result.video_url, API_BASE).toString()
  }, [result])

  function clearLiveConnections() {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }

  useEffect(() => {
    return () => clearLiveConnections()
  }, [])

  function applyJobSnapshot(snapshot) {
    setJob(snapshot)
    if (snapshot.status === 'done') {
      clearLiveConnections()
      setLoading(false)
      setResult({
        input_text: snapshot.input_text,
        gloss: snapshot.gloss,
        output_mode: 'video',
        video_url: snapshot.video_url,
      })
    }

    if (snapshot.status === 'failed') {
      clearLiveConnections()
      setLoading(false)
      setResult(null)
      setError(snapshot.error || 'Video-Job fehlgeschlagen')
    }
  }

  async function fetchJobStatus(jobId) {
    try {
      const response = await fetch(`${API_BASE}/api/jobs/${jobId}`)
      if (!response.ok) {
        throw new Error(`Job-Status Fehler: ${response.status}`)
      }
      const data = await response.json()
      applyJobSnapshot(data)
    } catch (err) {
      setError(err.message ?? 'Fehler beim Abrufen des Job-Status')
      clearLiveConnections()
      setLoading(false)
    }
  }

  function startJobPolling(jobId) {
    clearLiveConnections()
    pollRef.current = setInterval(() => {
      fetchJobStatus(jobId)
    }, 1000)
  }

  function startJobWebSocket(jobId) {
    const ws = new WebSocket(API_BASE.replace('http', 'ws') + `/ws/jobs/${jobId}`)
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        if (payload.type === 'job_update') {
          applyJobSnapshot(payload)
        }
      } catch {
        // Ignore invalid payloads; polling remains fallback.
      }
    }

    ws.onerror = () => {
      // Polling is the resilient fallback.
    }
  }

  async function submitGloss(textValue) {
    const response = await fetch(`${API_BASE}/api/translate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: textValue, output_mode: 'gloss' }),
    })

    if (!response.ok) {
      throw new Error(`API-Fehler: ${response.status}`)
    }

    const data = await response.json()
    setResult(data)
  }

  async function submitVideoJob(textValue) {
    const response = await fetch(`${API_BASE}/api/jobs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: textValue }),
    })

    if (!response.ok) {
      throw new Error(`Job-Erstellung fehlgeschlagen: ${response.status}`)
    }

    const createdJob = await response.json()
    setJob(createdJob)
    startJobPolling(createdJob.job_id)
    startJobWebSocket(createdJob.job_id)
  }

  async function onSubmit(event) {
    event.preventDefault()
    setLoading(true)
    setError('')
    setResult(null)
    setJob(null)

    try {
      if (mode === 'gloss') {
        clearLiveConnections()
        await submitGloss(text)
        setLoading(false)
        return
      }

      await submitVideoJob(text)
    } catch (err) {
      setError(err.message ?? 'Unbekannter Fehler')
      setLoading(false)
      clearLiveConnections()
    }
  }

  return (
    <main className="page">
      <section className="card">
        <h1>Text zu Gebaerdensprache</h1>
        <p className="lead">React-Frontend mit FastAPI-Backend fuer Gloss und asynchrone Video-Jobs.</p>

        <form onSubmit={onSubmit} className="form">
          <label>
            Eingabetext
            <textarea value={text} onChange={(e) => setText(e.target.value)} rows={5} required />
          </label>

          <label>
            Ausgabeformat
            <select value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="gloss">Gloss (sofort)</option>
              <option value="video">Video (asynchroner Job)</option>
            </select>
          </label>

          <button type="submit" disabled={loading}>
            {loading ? 'Verarbeite...' : 'Uebersetzen'}
          </button>
        </form>

        {error && <p className="error">{error}</p>}

        {job && (
          <div className="result">
            <h2>Video-Job</h2>
            <p><strong>Job-ID:</strong> {job.job_id}</p>
            <p><strong>Status:</strong> {job.status}</p>
            <p><strong>Fortschritt:</strong> {job.progress}%</p>
            {job.artifact_key && <p><strong>Artifact:</strong> {job.artifact_key}</p>}
            {wsJobUrl && <p><strong>WS Job-Channel:</strong> <code>{wsJobUrl}</code></p>}
          </div>
        )}

        {result && (
          <div className="result">
            <h2>Ergebnis</h2>
            <p><strong>Input:</strong> {result.input_text}</p>
            <p><strong>Gloss:</strong> {result.gloss}</p>
            <p><strong>Modus:</strong> {result.output_mode}</p>
            {result.sign_representation && (
              <p>
                <strong>Sign-Rep:</strong>{' '}
                <code>{JSON.stringify(result.sign_representation)}</code>
              </p>
            )}
            {resolvedVideoUrl && (
              <>
                <p><strong>Video-URL:</strong> {resolvedVideoUrl}</p>
                <video controls width="480" src={resolvedVideoUrl} />
              </>
            )}
          </div>
        )}

        <div className="hint">
          <strong>WebSocket Translate Endpoint:</strong> <code>{wsTranslateUrl}</code>
        </div>
      </section>
    </main>
  )
}

export default App
