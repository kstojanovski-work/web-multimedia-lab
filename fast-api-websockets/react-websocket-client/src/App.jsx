import { useEffect, useMemo, useRef, useState } from "react";

const DEFAULT_API_BASE = "ws://localhost:8000";

function App() {
  const [apiBase, setApiBase] = useState(DEFAULT_API_BASE);
  const [clientId, setClientId] = useState("alice");
  const [outgoingMessage, setOutgoingMessage] = useState("");
  const [messages, setMessages] = useState([]);
  const [status, setStatus] = useState("disconnected");
  const [activeConnections, setActiveConnections] = useState(0);
  const [socketEntries, setSocketEntries] = useState([]);
  const [isSocketWindowOpen, setIsSocketWindowOpen] = useState(false);

  const socketsRef = useRef(new Map());
  const activeSocketRef = useRef(null);

  const trimmedBase = useMemo(() => apiBase.trim().replace(/\/$/, ""), [apiBase]);
  const socketUrl = useMemo(() => {
    const trimmedClientId = clientId.trim() || "anonymous";
    return `${trimmedBase}/ws/${encodeURIComponent(trimmedClientId)}`;
  }, [trimmedBase, clientId]);

  const pushMessage = (value) => {
    setMessages((prev) => [...prev, value]);
  };

  const labelByReadyState = (readyState) => {
    if (readyState === WebSocket.CONNECTING) return "connecting";
    if (readyState === WebSocket.OPEN) return "open";
    if (readyState === WebSocket.CLOSING) return "closing";
    return "closed";
  };

  const syncSocketEntries = () => {
    const entries = Array.from(socketsRef.current.entries()).map(([reference, socket]) => ({
      reference,
      readyState: labelByReadyState(socket.readyState),
    }));

    setSocketEntries(entries);
    setActiveConnections(entries.filter((entry) => entry.readyState === "open").length);
    setStatus(entries.some((entry) => entry.readyState === "open") ? "connected" : "disconnected");
  };

  const disconnectByReference = (reference) => {
    const socket = socketsRef.current.get(reference);
    if (!socket) {
      return;
    }

    pushMessage(`disconnect requested: ${reference}`);

    try {
      socket.close();
      pushMessage(`disconnected: ${reference}`);
    } catch (_error) {
      // Ignore close errors from stale sockets.
      pushMessage(`disconnect failed: ${reference}`);
    }

    socketsRef.current.delete(reference);
    if (activeSocketRef.current === reference) {
      const nextReference = socketsRef.current.keys().next().value;
      activeSocketRef.current = nextReference ?? null;
    }
    syncSocketEntries();
  };

  const disconnectAllSockets = () => {
    const references = Array.from(socketsRef.current.keys());
    if (references.length === 0) {
      pushMessage("disconnect all requested: no active sockets");
      return;
    }

    pushMessage(`disconnect all requested: ${references.length} socket(s)`);
    for (const reference of references) {
      disconnectByReference(reference);
    }
    pushMessage("disconnect all completed");
  };

  const connect = () => {
    const trimmedClientId = clientId.trim() || "anonymous";
    const reference = `${trimmedClientId}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
    const socket = new WebSocket(`${trimmedBase}/ws/${encodeURIComponent(trimmedClientId)}`);

    socketsRef.current.set(reference, socket);
    activeSocketRef.current = reference;
    setStatus("connecting");
    syncSocketEntries();

    socket.onopen = () => {
      setStatus("connected");
      syncSocketEntries();
    };

    socket.onmessage = (event) => {
      pushMessage(`${reference}: ${event.data}`);
    };

    socket.onclose = () => {
      socketsRef.current.delete(reference);
      if (activeSocketRef.current === reference) {
        const nextReference = socketsRef.current.keys().next().value;
        activeSocketRef.current = nextReference ?? null;
      }
      syncSocketEntries();
    };

    socket.onerror = () => {
      pushMessage(`error: connection problem on ${reference}`);
      socketsRef.current.delete(reference);
      if (activeSocketRef.current === reference) {
        const nextReference = socketsRef.current.keys().next().value;
        activeSocketRef.current = nextReference ?? null;
      }
      syncSocketEntries();
    };
  };

  const sendMessage = () => {
    const message = outgoingMessage.trim();
    const activeReference = activeSocketRef.current;

    if (!message || !activeReference) {
      return;
    }

    const connection = socketsRef.current.get(activeReference);
    if (!connection || connection.readyState !== WebSocket.OPEN) {
      return;
    }

    connection.send(message);
    setOutgoingMessage("");
  };

  useEffect(() => {
    return () => {
      disconnectAllSockets();
    };
  }, []);

  return (
    <main className="page">
      <section className="panel">
        <h1>FastAPI WebSocket Client</h1>
        <p className="status">
          Status: <strong>{status}</strong>
        </p>
        <p className="status">
          Active connections: <strong>{activeConnections}</strong>
        </p>

        <label>
          WebSocket base URL
          <input
            value={apiBase}
            onChange={(event) => setApiBase(event.target.value)}
            placeholder="ws://localhost:8000"
          />
        </label>

        <label>
          Client ID
          <input
            value={clientId}
            onChange={(event) => setClientId(event.target.value)}
            placeholder="alice"
          />
        </label>

        <div className="button-row">
          <button onClick={connect} disabled={status === "connecting" && activeConnections === 0}>
            Connect
          </button>
          <button onClick={() => setIsSocketWindowOpen(true)} disabled={activeConnections <= 0}>
            Disconnect
          </button>
        </div>

        <p className="url">Next URL: {socketUrl}</p>

        <div className="send-row">
          <input
            value={outgoingMessage}
            onChange={(event) => setOutgoingMessage(event.target.value)}
            placeholder="Type a message"
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                sendMessage();
              }
            }}
          />
          <button onClick={sendMessage} disabled={activeConnections <= 0 || !outgoingMessage.trim()}>
            Send
          </button>
        </div>

        <ul className="messages">
          {messages.map((message, index) => (
            <li key={`${message}-${index}`}>{message}</li>
          ))}
        </ul>
        <div className="button-row">
          <button onClick={() => setMessages([])} disabled={messages.length === 0}>
            Clear Messages
          </button>
        </div>
      </section>

      {isSocketWindowOpen && (
        <section className="socket-window-backdrop" onClick={() => setIsSocketWindowOpen(false)}>
          <div className="socket-window" onClick={(event) => event.stopPropagation()}>
            <h2>Open Sockets</h2>
            <p className="status">Select sockets to disconnect.</p>
            <div className="socket-window-actions">
              <button onClick={disconnectAllSockets} disabled={socketEntries.length === 0}>
                Disconnect All
              </button>
              <button onClick={() => setIsSocketWindowOpen(false)}>Close</button>
            </div>

            <ul className="socket-list">
              {socketEntries.length === 0 && <li className="socket-item">No active sockets.</li>}
              {socketEntries.map((entry) => (
                <li key={entry.reference} className="socket-item">
                  <div>
                    <strong>{entry.reference}</strong>
                    <p>State: {entry.readyState}</p>
                  </div>
                  <button onClick={() => disconnectByReference(entry.reference)}>Disconnect</button>
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}
    </main>
  );
}

export default App;
