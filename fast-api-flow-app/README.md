# FastAPI Flow App

This project contains:
- `backend/`: FastAPI backend (session channel + WebRTC relay/signaling)
- `frontend/`: React frontend with two views:
  - `/customer`
  - `/agent`

## Implemented Use Case Flow

1. Customer clicks **Sign**:
- camera starts in customer view
- customer video is sent to backend via WebRTC
- backend relays the same stream to service-agent views via WebRTC
- backend handles WebRTC signaling (`offer`, `answer`)
- backend simulates sign-to-text and forwards recognized text updates to service-agent view

2. Customer clicks **Stop Translation**:
- camera/WebRTC streaming stops
- backend notifies service-agent view that signing stopped

3. Service agent sends response text:
- response is sent to backend
- backend forwards response text to customer view
- backend simulates text-to-sign video generation and notifies customer view

4. Customer clicks **End Session**:
- backend notifies service-agent view

The loop can be repeated multiple times within the same session.

## Run Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Run Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs by default on `http://localhost:5173`.

## Open Views

Use the same session id on both pages:
- `http://localhost:5173/customer?session=demo-session`
- `http://localhost:5173/agent?session=demo-session`

If backend URL differs, set:

```bash
VITE_BACKEND_URL=http://localhost:8000
```

For reliable ICE connectivity (avoid `checking -> disconnected`), configure the same ICE
servers on frontend and backend:

```bash
# frontend/.env
VITE_ICE_SERVERS=[{"urls":"stun:stun.l.google.com:19302"},{"urls":"turn:YOUR_TURN_HOST:3478?transport=udp","username":"USER","credential":"PASS"},{"urls":"turn:YOUR_TURN_HOST:3478?transport=tcp","username":"USER","credential":"PASS"}]
```

```bash
# backend env
WEBRTC_ICE_SERVERS=[{"urls":"stun:stun.l.google.com:19302"},{"urls":"turn:YOUR_TURN_HOST:3478?transport=udp","username":"USER","credential":"PASS"},{"urls":"turn:YOUR_TURN_HOST:3478?transport=tcp","username":"USER","credential":"PASS"}]
```
