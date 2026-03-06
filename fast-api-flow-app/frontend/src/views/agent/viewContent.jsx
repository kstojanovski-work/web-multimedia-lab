export default function AgentViewContent({
  sessionId,
  connected,
  agentId,
  remoteVideoRef,
  debugState,
  recognizedTexts,
  responseText,
  setResponseText,
  sendResponse,
  sessionEvents,
}) {
  return (
    <div className="view">
      <h1>Service-Agent View</h1>
      <p className="status">
        Session: {sessionId} | Signaling: {connected ? 'Connected' : 'Disconnected'} | Agent-ID:{' '}
        {agentId ?? 'pending'}
      </p>

      <div className="panel-row">
        <section className="panel">
          <h2>Incoming Customer Video</h2>
          <video ref={remoteVideoRef} playsInline autoPlay muted className="preview" />
          <p className="status">
            WebRTC: {debugState.connectionState} | ICE: {debugState.iceConnectionState} | Gathering:{' '}
            {debugState.iceGatheringState}
          </p>
          <p className="status">
            Stream: {debugState.hasRemoteStream ? 'yes' : 'no'} | Creating:{' '}
            {debugState.creatingPeer ? 'yes' : 'no'} | Last signal: {debugState.lastSignal}
          </p>
        </section>

        <section className="panel">
          <h2>Sign-to-Text Output</h2>
          <ul>
            {recognizedTexts.length === 0 && <li>No recognized text yet.</li>}
            {recognizedTexts.map((text, idx) => <li key={`${text}-${idx}`}>{text}</li>)}
          </ul>

          <h2>Send Response</h2>
          <div className="button-row">
            <input
              value={responseText}
              onChange={(e) => setResponseText(e.target.value)}
              placeholder="Type response for customer"
            />
            <button onClick={sendResponse}>Send</button>
          </div>

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
