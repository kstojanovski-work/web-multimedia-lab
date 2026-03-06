export default function CustomerViewContent({
  sessionId,
  connected,
  videoRef,
  isSigning,
  cameraReady,
  agentTexts,
  signVideoMessages,
  sessionEvents,
  startSign,
  stopSign,
  endSession,
}) {
  return (
    <div className="view">
      <h1>Customer View</h1>
      <p className="status">
        Session: {sessionId} | Signaling: {connected ? 'Connected' : 'Disconnected'}
      </p>
      <p className="status">Camera ready: {cameraReady ? 'yes' : 'no'}</p>
      <div className="panel-row">
        <section className="panel">
          <h2>Your Camera</h2>
          <video ref={videoRef} playsInline muted className="preview" />
          <div className="button-row">
            <button onClick={startSign} disabled={isSigning}>Sign</button>
            <button onClick={stopSign} disabled={!isSigning}>Stop Translation</button>
            <button className="danger" onClick={endSession}>End Session</button>
          </div>
        </section>

        <section className="panel">
          <h2>Service Agent Responses</h2>
          <ul>
            {agentTexts.length === 0 && <li>No response yet.</li>}
            {agentTexts.map((text, idx) => <li key={`${text}-${idx}`}>{text}</li>)}
          </ul>

          <h3>Text-to-Sign Output (Mocked)</h3>
          <ul>
            {signVideoMessages.length === 0 && <li>No generated sign video yet.</li>}
            {signVideoMessages.map((item, idx) => (
              <li key={`${item.text}-${idx}`}>
                Generated sign-video for: <strong>{item.text}</strong>
              </li>
            ))}
          </ul>

          <h3>Session Events</h3>
          <ul>
            {sessionEvents.length === 0 && <li>No events yet.</li>}
            {sessionEvents.map((item, idx) => <li key={`${item.message}-${idx}`}>{item.message}</li>)}
          </ul>
        </section>
      </div>
    </div>
  )
}
