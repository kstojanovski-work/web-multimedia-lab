# FastAPI + React WebRTC P2P Demo

This repository contains 2 projects:

- `backend/`: FastAPI WebSocket signaling server
- `frontend/`: React app using WebRTC for direct peer-to-peer media

## 1) Run backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 2) Run frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on `http://localhost:5173` by default.

## 3) Test P2P in two tabs

1. Open `http://localhost:5173` in tab 1 and tab 2.
2. Keep the same room id (default `demo-room`) in both tabs.
3. Click **Join Room** in each tab and allow camera/microphone access.
4. You should see/hear the other tab's stream.

## Notes

- Signaling is done via FastAPI WebSocket (`/ws/{room_id}/{peer_id}`).
- Media flows browser-to-browser over WebRTC once offer/answer + ICE exchange completes.
- Current signaling logic is optimized for a 1:1 call (two peers in same room).
