import { useEffect, useMemo, useRef, useState } from 'react'
import { useSessionSocket } from '../../shared/sessionSocket'
import { RTC_CONFIG } from '../../shared/rtcConfig'
import CustomerViewContent from './viewContent'

export default function CustomerView({ sessionId }) {
  const { connected, messages, send } = useSessionSocket('customer', sessionId)
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const peerRef = useRef(null)
  const videoSenderRef = useRef(null)
  const pendingIceRef = useRef([])
  const processedCountRef = useRef(0)
  const signClickAtRef = useRef(0)
  const [isSigning, setIsSigning] = useState(false)
  const [cameraReady, setCameraReady] = useState(false)

  const agentTexts = useMemo(
    () => messages.filter((m) => m.type === 'agent_text').map((m) => m.text),
    [messages],
  )

  const signVideoMessages = useMemo(
    () => messages.filter((m) => m.type === 'text_to_sign_video'),
    [messages],
  )

  const sessionEvents = useMemo(
    () => messages.filter((m) => m.type === 'session_event' || m.type === 'session_ended'),
    [messages],
  )

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null
    }
  }

  const ensureFreshCamera = async () => {
    stopCamera()
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        void videoRef.current.play()
      }
      setCameraReady(true)
      return true
    } catch {
      setCameraReady(false)
      return false
    }
  }

  const closePeer = () => {
    const peer = peerRef.current
    if (!peer) return
    peer.onicecandidate = null
    peer.onconnectionstatechange = null
    peer.close()
    peerRef.current = null
    videoSenderRef.current = null
    pendingIceRef.current = []
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

  const createPeer = async ({ force = false } = {}) => {
    if (!streamRef.current) return
    const existingPeer = peerRef.current
    if (
      !force &&
      existingPeer &&
      ['new', 'connecting', 'connected'].includes(existingPeer.connectionState)
    ) {
      return
    }
    closePeer()
    const peer = new RTCPeerConnection(RTC_CONFIG)
    peerRef.current = peer

    for (const track of streamRef.current.getTracks()) {
      const sender = peer.addTrack(track, streamRef.current)
      if (track.kind === 'video') {
        videoSenderRef.current = sender
      }
    }

    peer.onicecandidate = (event) => {
      if (!event.candidate) return
      send({ type: 'webrtc_ice_candidate', candidate: event.candidate.toJSON() })
    }

    peer.onconnectionstatechange = () => {
      if (['failed', 'closed'].includes(peer.connectionState)) {
        closePeer()
      }
    }

    const offer = await peer.createOffer()
    await peer.setLocalDescription(offer)
    if (signClickAtRef.current > 0) {
      console.info(
        '[customer-webrtc] offer sent',
        `t+${Math.round(performance.now() - signClickAtRef.current)}ms`,
      )
    }
    send({
      type: 'webrtc_offer',
      sdp: peer.localDescription,
    })
  }

  const startSign = async () => {
    if (isSigning) return
    signClickAtRef.current = performance.now()
    console.info('[customer-webrtc] sign click')

    const ready = await ensureFreshCamera()
    if (!ready) return
    if (!videoRef.current) {
      return
    }

    const videoTrack = streamRef.current?.getVideoTracks()?.[0]
    if (videoSenderRef.current && videoTrack) {
      try {
        await videoSenderRef.current.replaceTrack(videoTrack)
      } catch {
        // Fallback below will rebuild peer if sender replace fails.
      }
    }

    await createPeer({ force: true })
    send({ type: 'start_sign' })
    console.info(
      '[customer-webrtc] start_sign sent',
      `t+${Math.round(performance.now() - signClickAtRef.current)}ms`,
    )
    setIsSigning(true)
  }

  const stopSign = () => {
    if (!isSigning) return
    if (videoSenderRef.current) {
      void videoSenderRef.current.replaceTrack(null)
    }
    stopCamera()
    setCameraReady(false)
    send({ type: 'stop_sign' })
    setIsSigning(false)
  }

  const endSession = () => {
    stopSign()
    send({ type: 'end_session' })
  }

  useEffect(() => {
    const nextMessages = messages.slice(processedCountRef.current)
    processedCountRef.current = messages.length

    const handleAsync = async () => {
      for (const message of nextMessages) {
        if (message.type === 'webrtc_answer' && message.sdp) {
          const peer = peerRef.current
          if (!peer) continue
          if (peer.signalingState === 'closed') continue
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
      }
    }

    void handleAsync()
  }, [messages])

  useEffect(
    () => () => {
      closePeer()
      stopCamera()
    },
    [],
  )

  return (
    <CustomerViewContent
      sessionId={sessionId}
      connected={connected}
      videoRef={videoRef}
      isSigning={isSigning}
      cameraReady={cameraReady}
      agentTexts={agentTexts}
      signVideoMessages={signVideoMessages}
      sessionEvents={sessionEvents}
      startSign={startSign}
      stopSign={stopSign}
      endSession={endSession}
    />
  )
}
