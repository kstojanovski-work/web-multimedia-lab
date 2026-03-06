from collections import defaultdict
from typing import Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="WebRTC Signaling Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RoomManager:
    def __init__(self) -> None:
        self.rooms: Dict[str, Dict[str, WebSocket]] = defaultdict(dict)

    async def connect(self, room_id: str, peer_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.rooms[room_id][peer_id] = websocket

        # Notify existing peers that a new peer joined.
        await self.broadcast(
            room_id,
            {
                "type": "peer-joined",
                "peerId": peer_id,
            },
            exclude=peer_id,
        )

    async def disconnect(self, room_id: str, peer_id: str) -> None:
        room = self.rooms.get(room_id, {})
        room.pop(peer_id, None)

        await self.broadcast(
            room_id,
            {
                "type": "peer-left",
                "peerId": peer_id,
            },
            exclude=peer_id,
        )

        if not room:
            self.rooms.pop(room_id, None)

    async def broadcast(self, room_id: str, message: dict, exclude: str | None = None) -> None:
        for pid, ws in self.rooms.get(room_id, {}).items():
            if exclude is not None and pid == exclude:
                continue
            await ws.send_json(message)

    async def relay(self, room_id: str, from_peer: str, payload: dict) -> None:
        message = {
            "type": payload.get("type"),
            "from": from_peer,
            "data": payload.get("data"),
        }

        target = payload.get("to")
        if target:
            target_ws = self.rooms.get(room_id, {}).get(target)
            if target_ws:
                await target_ws.send_json(message)
            return

        await self.broadcast(room_id, message, exclude=from_peer)


manager = RoomManager()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.websocket("/ws/{room_id}/{peer_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, peer_id: str) -> None:
    await manager.connect(room_id, peer_id, websocket)

    # Tell the new peer who is already in the room.
    current_peers = [pid for pid in manager.rooms.get(room_id, {}) if pid != peer_id]
    await websocket.send_json({"type": "room-peers", "peers": current_peers})

    try:
        while True:
            payload = await websocket.receive_json()
            await manager.relay(room_id, peer_id, payload)
    except WebSocketDisconnect:
        await manager.disconnect(room_id, peer_id)
