import { useEffect, useMemo, useRef, useState } from "react";

type WsInbound = {
  type: "caption.partial" | "caption.final" | "error" | "session.ack";
  sessionId?: string;
  text?: string;
  confidence?: number;
  isFinal?: boolean;
  code?: string;
  message?: string;
  ts?: number;
};

const FPS = 10;
const WS_URL = import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws/live";

export function App() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const timerRef = useRef<number | null>(null);

  const [connected, setConnected] = useState(false);
  const [lastCaption, setLastCaption] = useState("");
  const [confidence, setConfidence] = useState(0);
  const [error, setError] = useState("");

  const sessionId = useMemo(() => crypto.randomUUID(), []);

  useEffect(() => {
    return () => {
      stopStreaming();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function startStreaming() {
    setError("");
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: 640, height: 360 },
      audio: false,
    });

    if (!videoRef.current) return;
    videoRef.current.srcObject = stream;
    await videoRef.current.play();

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      ws.send(
        JSON.stringify({
          type: "session.start",
          sessionId,
          fps: FPS,
          language: "de",
        })
      );

      timerRef.current = window.setInterval(() => sendFrame(), 1000 / FPS);
    };

    ws.onmessage = (event) => {
      const payload: WsInbound = JSON.parse(event.data);
      if (payload.type === "error") {
        setError(`${payload.code}: ${payload.message}`);
        return;
      }
      if (payload.type === "caption.partial" || payload.type === "caption.final") {
        setLastCaption(payload.text ?? "");
        setConfidence(payload.confidence ?? 0);
      }
    };

    ws.onclose = () => {
      setConnected(false);
    };
  }

  function stopStreaming() {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }

    wsRef.current?.close();
    wsRef.current = null;
    setConnected(false);

    const media = videoRef.current?.srcObject as MediaStream | null;
    media?.getTracks().forEach((track) => track.stop());
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  }

  function sendFrame() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const ws = wsRef.current;

    if (!video || !canvas || !ws || ws.readyState !== WebSocket.OPEN) return;

    const width = video.videoWidth;
    const height = video.videoHeight;
    if (!width || !height) return;

    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.drawImage(video, 0, 0, width, height);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.7);
    const payload = dataUrl.split(",")[1];

    ws.send(
      JSON.stringify({
        type: "frame.chunk",
        sessionId,
        seq: Date.now(),
        ts: performance.now(),
        encoding: "image/jpeg;base64",
        payload,
      })
    );
  }

  return (
    <main className="page">
      <h1>Live Sign-to-Text</h1>
      <p className="status">Status: {connected ? "verbunden" : "getrennt"}</p>

      <div className="video-wrap">
        <video ref={videoRef} autoPlay playsInline muted />
      </div>

      <canvas ref={canvasRef} className="hidden" />

      <section className="caption-box">
        <h2>Erkannter Text</h2>
        <p className="caption">{lastCaption || "..."}</p>
        <p className="confidence">Confidence: {confidence.toFixed(2)}</p>
      </section>

      <div className="actions">
        <button onClick={startStreaming} disabled={connected}>
          Start
        </button>
        <button onClick={stopStreaming} disabled={!connected}>
          Stop
        </button>
      </div>

      {error ? <p className="error">{error}</p> : null}
    </main>
  );
}
