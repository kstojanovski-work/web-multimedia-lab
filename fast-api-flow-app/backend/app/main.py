from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRelay
from aiortc.sdp import candidate_from_sdp, candidate_to_sdp
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState


@dataclass
class AgentState:
    websocket: WebSocket
    pc: RTCPeerConnection | None = None
    video_sender: Any | None = None
    negotiating: bool = False


@dataclass
class SessionState:
    customer: WebSocket | None = None
    agents: dict[str, AgentState] = field(default_factory=dict)
    customer_pc: RTCPeerConnection | None = None
    customer_video_track: Any | None = None
    customer_negotiating: bool = False
    recognized_counter: int = 0
    signing_active: bool = False
    recognized_task: asyncio.Task[None] | None = None


class SessionManager:
    def __init__(self) -> None:
        self.sessions: dict[str, SessionState] = defaultdict(SessionState)
        self._lock = asyncio.Lock()
        self._relay = MediaRelay()
        self._rtc_configuration = self._build_rtc_configuration()

    def _build_rtc_configuration(self) -> RTCConfiguration:
        raw = os.getenv("WEBRTC_ICE_SERVERS", "").strip()
        turn_url = os.getenv("WEBRTC_TURN_URL", "").strip()
        turn_username = os.getenv("WEBRTC_TURN_USERNAME", "").strip()
        turn_credential = os.getenv("WEBRTC_TURN_CREDENTIAL", "").strip()

        if turn_url:
            return RTCConfiguration(
                iceServers=[
                    RTCIceServer(urls="stun:stun.l.google.com:19302"),
                    RTCIceServer(
                        urls=turn_url,
                        username=turn_username or None,
                        credential=turn_credential or None,
                    ),
                ]
            )

        if not raw:
            return RTCConfiguration(iceServers=[RTCIceServer(urls="stun:stun.l.google.com:19302")])

        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            items = []

        servers: list[RTCIceServer] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            urls = item.get("urls")
            if not urls:
                continue
            username = item.get("username")
            credential = item.get("credential")
            servers.append(
                RTCIceServer(urls=urls, username=username, credential=credential)
            )

        if not servers:
            servers = [RTCIceServer(urls="stun:stun.l.google.com:19302")]
        return RTCConfiguration(iceServers=servers)

    async def add_customer_ice_candidate(
        self, session_id: str, candidate: dict[str, Any]
    ) -> None:
        session = self.sessions.get(session_id)
        if not session or not session.customer_pc:
            return
        await self._add_ice_candidate(session.customer_pc, candidate)

    async def add_agent_ice_candidate(
        self, session_id: str, agent_id: str, candidate: dict[str, Any]
    ) -> None:
        session = self.sessions.get(session_id)
        if not session:
            return
        agent = session.agents.get(agent_id)
        if not agent or not agent.pc:
            return
        await self._add_ice_candidate(agent.pc, candidate)

    async def _add_ice_candidate(
        self, pc: RTCPeerConnection, candidate: dict[str, Any]
    ) -> None:
        raw = (candidate or {}).get("candidate")
        if not raw:
            return
        try:
            normalized = raw[10:] if raw.startswith("candidate:") else raw
            ice = candidate_from_sdp(normalized)
            ice.sdpMid = candidate.get("sdpMid")
            ice.sdpMLineIndex = candidate.get("sdpMLineIndex")
            await pc.addIceCandidate(ice)
        except Exception as exc:
            # Ignore malformed / late candidates during reconnect churn.
            print(f"[webrtc] failed to add ICE candidate: {exc}")
            return

    def _candidate_to_payload(self, candidate: Any) -> dict[str, Any]:
        return {
            "candidate": f"candidate:{candidate_to_sdp(candidate)}",
            "sdpMid": candidate.sdpMid,
            "sdpMLineIndex": candidate.sdpMLineIndex,
        }

    async def connect(self, session_id: str, role: str, websocket: WebSocket) -> str:
        await websocket.accept()
        async with self._lock:
            session = self.sessions[session_id]
            if role == "customer":
                session.customer = websocket
                return "customer"

            agent_id = uuid.uuid4().hex
            session.agents[agent_id] = AgentState(websocket=websocket)
            return agent_id

    async def disconnect(
        self, session_id: str, role: str, websocket: WebSocket
    ) -> str | None:
        disconnected_id: str | None = None
        session = self.sessions.get(session_id)
        if not session:
            return None

        if role == "customer" and session.customer == websocket:
            session.customer = None
            disconnected_id = "customer"
            await self.close_customer_media(session_id)
            await self.stop_signing(session_id)

        if role == "agent":
            for agent_id, agent in list(session.agents.items()):
                if agent.websocket == websocket:
                    await self.close_agent_media(session_id, agent_id)
                    session.agents.pop(agent_id, None)
                    disconnected_id = agent_id
                    break

        if session.customer is None and not session.agents:
            self.sessions.pop(session_id, None)

        return disconnected_id

    async def close_customer_media(self, session_id: str) -> None:
        session = self.sessions.get(session_id)
        if not session:
            return

        if session.customer_pc:
            await session.customer_pc.close()
            session.customer_pc = None

        session.customer_video_track = None
        self._attach_customer_track_to_agents(session, None)

    async def close_agent_media(self, session_id: str, agent_id: str) -> None:
        session = self.sessions.get(session_id)
        if not session:
            return

        agent = session.agents.get(agent_id)
        if not agent:
            return

        if agent.pc:
            await agent.pc.close()
            agent.pc = None
        agent.video_sender = None

    def _attach_customer_track_to_agents(self, session: SessionState, track: Any | None) -> None:
        for agent in session.agents.values():
            if not agent.video_sender:
                continue
            if track is None:
                agent.video_sender.replaceTrack(None)
            else:
                agent.video_sender.replaceTrack(self._relay.subscribe(track))

    async def broadcast_to_agents(self, session_id: str, payload: dict[str, Any]) -> None:
        session = self.sessions.get(session_id)
        if not session:
            return
        for agent_id, agent in list(session.agents.items()):
            sent = await self._safe_send_json(agent.websocket, payload)
            if not sent:
                await self.close_agent_media(session_id, agent_id)
                session.agents.pop(agent_id, None)

    async def send_to_customer(self, session_id: str, payload: dict[str, Any]) -> None:
        session = self.sessions.get(session_id)
        if not session or not session.customer:
            return
        sent = await self._safe_send_json(session.customer, payload)
        if not sent:
            session.customer = None

    async def send_to_agent(
        self, session_id: str, agent_id: str, payload: dict[str, Any]
    ) -> None:
        session = self.sessions.get(session_id)
        if not session:
            return
        agent = session.agents.get(agent_id)
        if not agent:
            return
        sent = await self._safe_send_json(agent.websocket, payload)
        if not sent:
            await self.close_agent_media(session_id, agent_id)
            session.agents.pop(agent_id, None)

    async def _safe_send_json(self, websocket: WebSocket, payload: dict[str, Any]) -> bool:
        if (
            websocket.client_state != WebSocketState.CONNECTED
            or websocket.application_state != WebSocketState.CONNECTED
        ):
            return False
        try:
            await websocket.send_json(payload)
            return True
        except (WebSocketDisconnect, RuntimeError):
            return False
        except Exception:
            return False

    async def notify_session(self, session_id: str, payload: dict[str, Any]) -> None:
        await asyncio.gather(
            self.send_to_customer(session_id, payload),
            self.broadcast_to_agents(session_id, payload),
            return_exceptions=True,
        )

    def next_recognized_text(self, session_id: str) -> str:
        session = self.sessions[session_id]
        session.recognized_counter += 1
        idx = session.recognized_counter
        return f"Recognized sign phrase #{idx} at {time.strftime('%H:%M:%S')}"

    async def start_signing(self, session_id: str) -> None:
        session = self.sessions[session_id]
        session.signing_active = True
        if session.customer_video_track is not None:
            self._attach_customer_track_to_agents(session, session.customer_video_track)
        if session.recognized_task and not session.recognized_task.done():
            return
        session.recognized_task = asyncio.create_task(self._recognized_loop(session_id))

    async def stop_signing(self, session_id: str) -> None:
        session = self.sessions.get(session_id)
        if not session:
            return
        session.signing_active = False
        self._attach_customer_track_to_agents(session, None)
        if session.recognized_task and not session.recognized_task.done():
            session.recognized_task.cancel()
            try:
                await session.recognized_task
            except asyncio.CancelledError:
                pass
        session.recognized_task = None

    async def _recognized_loop(self, session_id: str) -> None:
        try:
            while True:
                await asyncio.sleep(1)
                session = self.sessions.get(session_id)
                if not session or not session.signing_active:
                    return
                recognized = self.next_recognized_text(session_id)
                await self.broadcast_to_agents(
                    session_id,
                    {"type": "recognized_text", "text": recognized},
                )
        except asyncio.CancelledError:
            pass

    def has_customer_video_track(self, session_id: str) -> bool:
        session = self.sessions.get(session_id)
        return bool(session and session.customer_video_track is not None)

    async def handle_webrtc_offer(
        self,
        session_id: str,
        role: str,
        participant_id: str,
        sdp: dict[str, Any],
    ) -> dict[str, Any] | None:
        if sdp.get("type") != "offer" or not sdp.get("sdp"):
            return None

        if role == "customer":
            return await self._handle_customer_offer(session_id, sdp)

        if role == "agent":
            return await self._handle_agent_offer(session_id, participant_id, sdp)

        return None

    async def _handle_customer_offer(
        self, session_id: str, sdp: dict[str, Any]
    ) -> dict[str, Any] | None:
        session = self.sessions[session_id]
        if session.customer_negotiating:
            return None

        session.customer_negotiating = True
        await self.close_customer_media(session_id)

        pc = RTCPeerConnection(configuration=self._rtc_configuration)
        session.customer_pc = pc

        @pc.on("track")
        def on_track(track: Any) -> None:
            if track.kind != "video":
                return
            session.customer_video_track = track
            if session.signing_active:
                self._attach_customer_track_to_agents(session, track)
                asyncio.create_task(
                    self.broadcast_to_agents(session_id, {"type": "stream_available"})
                )

        @pc.on("connectionstatechange")
        async def on_connectionstatechange() -> None:
            if pc.connectionState in {"failed", "closed", "disconnected"}:
                if session.customer_pc == pc:
                    session.customer_video_track = None
                    for agent in session.agents.values():
                        if agent.video_sender:
                            agent.video_sender.replaceTrack(None)

        @pc.on("icecandidate")
        def on_icecandidate(candidate: Any) -> None:
            if not candidate:
                return
            asyncio.create_task(
                self.send_to_customer(
                    session_id,
                    {
                        "type": "webrtc_ice_candidate",
                        "candidate": self._candidate_to_payload(candidate),
                    },
                )
            )

        try:
            await pc.setRemoteDescription(
                RTCSessionDescription(sdp=sdp["sdp"], type=sdp["type"])
            )
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)

            return {
                "type": "webrtc_answer",
                "sdp": {
                    "type": pc.localDescription.type,
                    "sdp": pc.localDescription.sdp,
                },
            }
        finally:
            session.customer_negotiating = False

    async def _handle_agent_offer(
        self, session_id: str, agent_id: str, sdp: dict[str, Any]
    ) -> dict[str, Any] | None:
        session = self.sessions.get(session_id)
        if not session:
            return None

        agent = session.agents.get(agent_id)
        if not agent:
            return None

        if agent.negotiating:
            return None

        agent.negotiating = True
        await self.close_agent_media(session_id, agent_id)

        pc = RTCPeerConnection(configuration=self._rtc_configuration)
        agent.pc = pc
        transceiver = pc.addTransceiver("video", direction="sendonly")
        agent.video_sender = transceiver.sender

        if session.customer_video_track is not None:
            if session.signing_active:
                agent.video_sender.replaceTrack(self._relay.subscribe(session.customer_video_track))

        @pc.on("connectionstatechange")
        async def on_connectionstatechange() -> None:
            if pc.connectionState in {"failed", "closed", "disconnected"}:
                if agent.pc == pc:
                    await self.close_agent_media(session_id, agent_id)

        @pc.on("icecandidate")
        def on_icecandidate(candidate: Any) -> None:
            if not candidate:
                return
            asyncio.create_task(
                self.send_to_agent(
                    session_id,
                    agent_id,
                    {
                        "type": "webrtc_ice_candidate",
                        "candidate": self._candidate_to_payload(candidate),
                    },
                )
            )

        try:
            await pc.setRemoteDescription(
                RTCSessionDescription(sdp=sdp["sdp"], type=sdp["type"])
            )
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)

            return {
                "type": "webrtc_answer",
                "sdp": {
                    "type": pc.localDescription.type,
                    "sdp": pc.localDescription.sdp,
                },
            }
        finally:
            agent.negotiating = False


app = FastAPI(title="FastAPI Flow Backend")
manager = SessionManager()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws/{role}/{session_id}")
async def ws_endpoint(websocket: WebSocket, role: str, session_id: str) -> None:
    if role not in {"customer", "agent"}:
        await websocket.close(code=1008, reason="Unsupported role")
        return

    participant_id = await manager.connect(session_id, role, websocket)
    await manager.notify_session(
        session_id,
        {
            "type": "session_event",
            "session_id": session_id,
            "message": f"{role} joined session",
            "participant_id": participant_id,
        },
    )
    if role == "agent":
        await manager.send_to_agent(
            session_id,
            participant_id,
            {"type": "agent_registered", "agent_id": participant_id},
        )

    try:
        while True:
            try:
                message = await websocket.receive_json()
            except RuntimeError as exc:
                if "WebSocket is not connected" in str(exc):
                    break
                raise

            event_type = message.get("type")

            if role == "customer":
                if event_type == "start_sign":
                    await manager.start_signing(session_id)
                    await manager.broadcast_to_agents(
                        session_id, {"type": "sign_status", "status": "started"}
                    )
                    if manager.has_customer_video_track(session_id):
                        await manager.broadcast_to_agents(
                            session_id, {"type": "stream_available"}
                        )
                elif event_type == "stop_sign":
                    await manager.stop_signing(session_id)
                    await manager.broadcast_to_agents(
                        session_id, {"type": "sign_status", "status": "stopped"}
                    )
                elif event_type == "webrtc_offer":
                    answer = await manager.handle_webrtc_offer(
                        session_id, role, participant_id, message.get("sdp") or {}
                    )
                    if answer:
                        offer_id = message.get("offer_id")
                        if offer_id:
                            answer["offer_id"] = offer_id
                        await manager.send_to_customer(session_id, answer)
                elif event_type == "webrtc_ice_candidate":
                    candidate = message.get("candidate") or {}
                    await manager.add_customer_ice_candidate(session_id, candidate)
                elif event_type == "end_session":
                    await manager.stop_signing(session_id)
                    await manager.close_customer_media(session_id)
                    await manager.broadcast_to_agents(
                        session_id,
                        {
                            "type": "session_ended",
                            "message": "Customer ended the session",
                        },
                    )

            if role == "agent":
                if event_type == "agent_response_text":
                    response_text = (message.get("text") or "").strip()
                    if response_text:
                        await manager.send_to_customer(
                            session_id,
                            {
                                "type": "agent_text",
                                "text": response_text,
                            },
                        )
                        await manager.send_to_customer(
                            session_id,
                            {
                                "type": "text_to_sign_video",
                                "video_url": f"/mock-sign-video?text={response_text}",
                                "text": response_text,
                            },
                        )
                elif event_type == "webrtc_offer":
                    answer = await manager.handle_webrtc_offer(
                        session_id, role, participant_id, message.get("sdp") or {}
                    )
                    if answer:
                        offer_id = message.get("offer_id")
                        if offer_id:
                            answer["offer_id"] = offer_id
                        await manager.send_to_agent(session_id, participant_id, answer)
                elif event_type == "webrtc_ice_candidate":
                    candidate = message.get("candidate") or {}
                    await manager.add_agent_ice_candidate(
                        session_id, participant_id, candidate
                    )

    except WebSocketDisconnect:
        pass
    finally:
        disconnected_id = await manager.disconnect(session_id, role, websocket)
        await manager.notify_session(
            session_id,
            {
                "type": "session_event",
                "session_id": session_id,
                "message": f"{role} left session",
                "participant_id": disconnected_id,
            },
        )


@app.get("/mock-sign-video")
def mock_sign_video(text: str) -> dict[str, str]:
    return {"status": "generated", "text": text, "video_note": "Mock video placeholder"}
