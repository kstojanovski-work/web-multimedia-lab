import { useEffect, useMemo, useRef, useState } from 'react'
import { useSessionSocket } from '../../shared/sessionSocket'
import { RTC_CONFIG } from '../../shared/rtcConfig'
import AgentViewContent from './viewContent'

export default function AgentView({ sessionId }) {
  const { connected, messages, send } = useSessionSocket('agent', sessionId)
  const [responseText, setResponseText] = useState('')
  const [agentId, setAgentId] = useState(null)
  const [expectStream, setExpectStream] = useState(false)
  const [debugState, setDebugState] = useState({
    creatingPeer: false,
    connectionState: 'none',
    iceGatheringState: 'none',
    iceConnectionState: 'none',
    hasRemoteStream: false,
    lastSignal: 'none',
  })
  const remoteVideoRef = useRef(null)
  const peerRef = useRef(null)
  const pendingIceRef = useRef([])
  const creatingPeerRef = useRef(false)
  const lastCreateAtRef = useRef(0)
  const awaitingAnswerRef = useRef(false)
  const offerSentAtRef = useRef(0)
  const offerRetryCountRef = useRef(0)
  const currentOfferIdRef = useRef('')
  const processedCountRef = useRef(0)
  const signStartedAtRef = useRef(0)
  const firstFrameLoggedRef = useRef(false)

  const recognizedTexts = useMemo(
    () => messages.filter((m) => m.type === 'recognized_text').map((m) => m.text),
    [messages],
  )
  const sessionEvents = useMemo(
    () => messages.filter((m) => m.type === 'session_event' || m.type === 'session_ended'),
    [messages],
  )

  const closePeer = () => {
    console.info('[agent-webrtc] closePeer')
    if (peerRef.current) {
      peerRef.current.ontrack = null
      peerRef.current.onicecandidate = null
      peerRef.current.onconnectionstatechange = null
      peerRef.current.oniceconnectionstatechange = null
      peerRef.current.onicegatheringstatechange = null
      peerRef.current.close()
      peerRef.current = null
    }
    if (remoteVideoRef.current) {
      remoteVideoRef.current.srcObject = null
    }
    pendingIceRef.current = []
    awaitingAnswerRef.current = false
    offerSentAtRef.current = 0
    offerRetryCountRef.current = 0
    currentOfferIdRef.current = ''
    setDebugState((prev) => ({
      ...prev,
      connectionState: 'closed',
      hasRemoteStream: false,
    }))
  }

  const flushPendingIce = async (peer) => {
    if (!peer.remoteDescription || pendingIceRef.current.length === 0) return
    const queued = [...pendingIceRef.current]
    pendingIceRef.current = []
    for (const candidate of queued) {
      try {
        await peer.addIceCandidate(new RTCIceCandidate(candidate))
      } catch {
        // Ignore stale/invalid signaling data.
      }
    }
  }

  const attachRemoteStream = (stream) => {
    if (!remoteVideoRef.current) return
    const videoEl = remoteVideoRef.current
    if (videoEl.srcObject !== stream) {
      videoEl.srcObject = stream
    }

    const tryPlay = async () => {
      try {
        await videoEl.play()
      } catch {
        // Retry a few times; some browsers delay playback readiness.
      }
    }

    videoEl.onloadedmetadata = () => {
      void tryPlay()
    }
    videoEl.onplaying = () => {
      if (firstFrameLoggedRef.current) return
      firstFrameLoggedRef.current = true
      const delta = signStartedAtRef.current
        ? Math.round(performance.now() - signStartedAtRef.current)
        : -1
      console.info('[agent-webrtc] first video playing', delta >= 0 ? `t+${delta}ms` : '')
    }
    void tryPlay()
    setTimeout(() => void tryPlay(), 120)
    setTimeout(() => void tryPlay(), 300)
    if ('requestVideoFrameCallback' in videoEl) {
      videoEl.requestVideoFrameCallback(() => {
        if (firstFrameLoggedRef.current) return
        firstFrameLoggedRef.current = true
        const delta = signStartedAtRef.current
          ? Math.round(performance.now() - signStartedAtRef.current)
          : -1
        console.info('[agent-webrtc] first video frame', delta >= 0 ? `t+${delta}ms` : '')
      })
    }
  }

  const createPeer = async ({ force = false } = {}) => {
    const now = Date.now()
    const existingPeer = peerRef.current
    if (
      !force &&
      existingPeer &&
      ['new', 'connecting', 'connected'].includes(existingPeer.connectionState)
    ) {
      return
    }
    if (creatingPeerRef.current) return
    if (!force && now - lastCreateAtRef.current < 250) return

    creatingPeerRef.current = true
    setDebugState((prev) => ({ ...prev, creatingPeer: true }))
    lastCreateAtRef.current = now
    closePeer()
    const peer = new RTCPeerConnection(RTC_CONFIG)
    console.info('[agent-webrtc] createPeer start')
    peerRef.current = peer
    setDebugState((prev) => ({ ...prev, connectionState: 'connecting' }))
    peer.addTransceiver('video', { direction: 'recvonly' })

    peer.ontrack = async (event) => {
      console.info('[agent-webrtc] ontrack', event.streams?.length ?? 0)
      if (!remoteVideoRef.current) return

      const remoteStream = event.streams?.[0] ?? new MediaStream([event.track])
      attachRemoteStream(remoteStream)
      setDebugState((prev) => ({ ...prev, hasRemoteStream: true }))

      event.track.onunmute = () => {
        attachRemoteStream(remoteStream)
      }
      event.track.onended = () => {
        setDebugState((prev) => ({ ...prev, hasRemoteStream: false }))
      }
    }
    peer.onicecandidate = (event) => {
      if (!event.candidate) return
      send({ type: 'webrtc_ice_candidate', candidate: event.candidate.toJSON() })
    }

    peer.onconnectionstatechange = () => {
      console.info('[agent-webrtc] connectionState', peer.connectionState)
      setDebugState((prev) => ({ ...prev, connectionState: peer.connectionState }))
      if (['failed', 'closed'].includes(peer.connectionState)) {
        closePeer()
      }
    }
    peer.oniceconnectionstatechange = () => {
      console.info('[agent-webrtc] iceConnectionState', peer.iceConnectionState)
      setDebugState((prev) => ({ ...prev, iceConnectionState: peer.iceConnectionState }))
    }
    peer.onicegatheringstatechange = () => {
      setDebugState((prev) => ({ ...prev, iceGatheringState: peer.iceGatheringState }))
    }

    try {
      const offer = await peer.createOffer()
      await peer.setLocalDescription(offer)
      console.info('[agent-webrtc] send offer')
      awaitingAnswerRef.current = true
      offerSentAtRef.current = performance.now()
      const offerId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
      currentOfferIdRef.current = offerId
      send({ type: 'webrtc_offer', sdp: peer.localDescription, offer_id: offerId })
    } finally {
      creatingPeerRef.current = false
      setDebugState((prev) => ({ ...prev, creatingPeer: false }))
    }
  }

  useEffect(() => {
    const nextMessages = messages.slice(processedCountRef.current)
    processedCountRef.current = messages.length

    const handleAsync = async () => {
      for (const message of nextMessages) {
        if (message.type === 'agent_registered' && message.agent_id) {
          setAgentId(message.agent_id)
          setDebugState((prev) => ({ ...prev, lastSignal: 'agent_registered' }))
        }

        if (message.type === 'webrtc_answer' && message.sdp) {
          if (message.offer_id && message.offer_id !== currentOfferIdRef.current) {
            console.info('[agent-webrtc] stale answer ignored', message.offer_id)
            continue
          }
          console.info('[agent-webrtc] received answer')
          awaitingAnswerRef.current = false
          offerRetryCountRef.current = 0
          setDebugState((prev) => ({ ...prev, lastSignal: 'webrtc_answer' }))
          const peer = peerRef.current
          if (!peer) continue
          try {
            await peer.setRemoteDescription(new RTCSessionDescription(message.sdp))
            await flushPendingIce(peer)
          } catch {
            // Ignore stale/invalid signaling data.
          }
        }

        if (message.type === 'webrtc_ice_candidate' && message.candidate) {
          const peer = peerRef.current
          if (!peer) continue
          if (!peer.remoteDescription) {
            pendingIceRef.current.push(message.candidate)
            continue
          }
          try {
            await peer.addIceCandidate(new RTCIceCandidate(message.candidate))
          } catch {
            // Ignore stale/invalid signaling data.
          }
        }

        if (message.type === 'stream_available') {
          console.info('[agent-webrtc] stream_available')
          if (signStartedAtRef.current > 0) {
            console.info(
              '[agent-webrtc] stream_available after start',
              `t+${Math.round(performance.now() - signStartedAtRef.current)}ms`,
            )
          }
          setDebugState((prev) => ({ ...prev, lastSignal: 'stream_available' }))
          setExpectStream(true)
          const hasRemoteStream = Boolean(remoteVideoRef.current?.srcObject)
          const state = peerRef.current?.connectionState
          if (
            connected &&
            !hasRemoteStream &&
            (!state || ['failed', 'closed', 'disconnected'].includes(state))
          ) {
            await createPeer()
          }
        }

        if (message.type === 'stream_not_ready') {
          console.info('[agent-webrtc] stream_not_ready')
          setDebugState((prev) => ({ ...prev, lastSignal: 'stream_not_ready' }))
          // Keep current peer alive; a late "stream_not_ready" for an older offer
          // must not tear down an active/newer negotiation.
        }

        if (message.type === 'sign_status') {
          setDebugState((prev) => ({ ...prev, lastSignal: `sign_status:${message.status}` }))
          if (message.status === 'started') {
            signStartedAtRef.current = performance.now()
            firstFrameLoggedRef.current = false
            offerRetryCountRef.current = 0
            console.info('[agent-webrtc] sign_status started')
            setExpectStream(true)
            const hasRemoteStream = Boolean(remoteVideoRef.current?.srcObject)
            if (connected && !hasRemoteStream) {
              await createPeer({ force: true })
            }
          }
        }

        if (message.type === 'session_ended') {
          setExpectStream(false)
          closePeer()
        }
      }
    }

    void handleAsync()
  }, [messages])

  useEffect(() => {
    if (!connected) {
      closePeer()
      return
    }
    void createPeer()
  }, [connected])

  useEffect(() => {
    if (!connected || !expectStream) return
    const interval = setInterval(() => {
      const hasRemoteStream = Boolean(remoteVideoRef.current?.srcObject)
      const state = peerRef.current?.connectionState
      if (state && ['new', 'connecting', 'connected'].includes(state)) {
        if (
          awaitingAnswerRef.current &&
          offerSentAtRef.current > 0 &&
          performance.now() - offerSentAtRef.current > 6000 &&
          offerRetryCountRef.current < 1
        ) {
          console.info('[agent-webrtc] offer timeout -> retry')
          offerRetryCountRef.current += 1
          void createPeer({ force: true })
        }
        return
      }
      if (!hasRemoteStream) {
        void createPeer()
      }
    }, 700)
    return () => clearInterval(interval)
  }, [connected, expectStream])

  useEffect(() => closePeer, [])

  const sendResponse = () => {
    const text = responseText.trim()
    if (!text) return
    send({ type: 'agent_response_text', text })
    setResponseText('')
  }

  return (
    <AgentViewContent
      sessionId={sessionId}
      connected={connected}
      agentId={agentId}
      remoteVideoRef={remoteVideoRef}
      debugState={debugState}
      recognizedTexts={recognizedTexts}
      responseText={responseText}
      setResponseText={setResponseText}
      sendResponse={sendResponse}
      sessionEvents={sessionEvents}
    />
  )
}
