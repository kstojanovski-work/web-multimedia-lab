import { useEffect, useMemo, useRef, useState } from "react";

const SIGNALING_URL = import.meta.env.VITE_SIGNALING_URL || "ws://localhost:8000";
const ICE_SERVERS = [{ urls: "stun:stun.l.google.com:19302" }];

function App() {
  const [roomId, setRoomId] = useState("demo-room");
  const [connected, setConnected] = useState(false);
  const [status, setStatus] = useState("Idle");

  const peerId = useMemo(() => crypto.randomUUID(), []);

  const wsRef = useRef(null);
  const pcRef = useRef(null);
  const localStreamRef = useRef(null);
  const remoteStreamRef = useRef(new MediaStream());

  const localVideoRef = useRef(null);
  const remoteVideoRef = useRef(null);

  useEffect(() => {
    return () => {
      cleanup();
    };
  }, []);

  const cleanup = () => {
    wsRef.current?.close();
    wsRef.current = null;

    if (pcRef.current) {
      pcRef.current.ontrack = null;
      pcRef.current.onicecandidate = null;
      pcRef.current.close();
      pcRef.current = null;
    }

    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach((track) => track.stop());
      localStreamRef.current = null;
    }

    remoteStreamRef.current.getTracks().forEach((track) => {
      remoteStreamRef.current.removeTrack(track);
    });

    if (localVideoRef.current) {
      localVideoRef.current.srcObject = null;
    }

    if (remoteVideoRef.current) {
      remoteVideoRef.current.srcObject = null;
    }

    setConnected(false);
    setStatus("Disconnected");
  };

  const ensureLocalMedia = async () => {
    if (localStreamRef.current) {
      return localStreamRef.current;
    }

    const stream = await navigator.mediaDevices.getUserMedia({
      video: true,
      audio: true,
    });
    localStreamRef.current = stream;
    if (localVideoRef.current) {
      localVideoRef.current.srcObject = stream;
    }
    return stream;
  };

  const sendSignal = (payload) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload));
    }
  };

  const createPeerConnection = async () => {
    if (pcRef.current) {
      return pcRef.current;
    }

    const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });

    pc.ontrack = (event) => {
      event.streams[0].getTracks().forEach((track) => {
        remoteStreamRef.current.addTrack(track);
      });

      if (remoteVideoRef.current) {
        remoteVideoRef.current.srcObject = remoteStreamRef.current;
      }
    };

    pc.onicecandidate = (event) => {
      if (event.candidate) {
        sendSignal({
          type: "ice-candidate",
          data: event.candidate,
        });
      }
    };

    const stream = await ensureLocalMedia();
    stream.getTracks().forEach((track) => pc.addTrack(track, stream));

    pcRef.current = pc;
    return pc;
  };

  const makeOffer = async () => {
    setStatus("Creating offer...");
    const pc = await createPeerConnection();

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    sendSignal({
      type: "offer",
      data: offer,
    });

    setStatus("Offer sent. Waiting for answer...");
  };

  const handleSignalMessage = async (message) => {
    if (message.type === "room-peers") {
      if (message.peers.length > 0) {
        await makeOffer();
      }
      return;
    }

    if (message.type === "peer-joined") {
      if (connected) {
        await makeOffer();
      }
      return;
    }

    if (message.type === "peer-left") {
      setStatus("Peer left the room.");
      return;
    }

    if (message.type === "offer") {
      setStatus("Offer received. Creating answer...");
      const pc = await createPeerConnection();
      await pc.setRemoteDescription(new RTCSessionDescription(message.data));

      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);

      sendSignal({
        type: "answer",
        to: message.from,
        data: answer,
      });

      setStatus("Answer sent.");
      return;
    }

    if (message.type === "answer") {
      const pc = pcRef.current;
      if (!pc) {
        return;
      }

      await pc.setRemoteDescription(new RTCSessionDescription(message.data));
      setStatus("Connected: media should flow now.");
      return;
    }

    if (message.type === "ice-candidate") {
      const pc = pcRef.current;
      if (!pc) {
        return;
      }

      try {
        await pc.addIceCandidate(new RTCIceCandidate(message.data));
      } catch (error) {
        console.error("Failed to add ICE candidate", error);
      }
    }
  };

  const joinRoom = async () => {
    cleanup();
    setStatus("Getting camera/microphone access...");
    await ensureLocalMedia();

    const ws = new WebSocket(`${SIGNALING_URL}/ws/${roomId}/${peerId}`);

    ws.onopen = () => {
      wsRef.current = ws;
      setConnected(true);
      setStatus(`Connected to signaling server in room: ${roomId}`);
    };

    ws.onmessage = async (event) => {
      const message = JSON.parse(event.data);
      await handleSignalMessage(message);
    };

    ws.onclose = () => {
      setConnected(false);
      setStatus("Signaling socket closed.");
    };

    ws.onerror = () => {
      setStatus("WebSocket error.");
    };
  };

  return (
    <div className="page">
      <h1>WebRTC P2P Video Demo</h1>

      <div className="controls">
        <input
          value={roomId}
          onChange={(e) => setRoomId(e.target.value)}
          placeholder="Room ID"
        />
        <button onClick={joinRoom} disabled={connected}>
          Join Room
        </button>
        <button onClick={cleanup}>Leave</button>
      </div>

      <p className="status">Status: {status}</p>

      <div className="videos">
        <div>
          <h2>Local</h2>
          <video ref={localVideoRef} autoPlay playsInline muted />
        </div>

        <div>
          <h2>Remote</h2>
          <video ref={remoteVideoRef} autoPlay playsInline />
        </div>
      </div>
    </div>
  );
}

export default App;
