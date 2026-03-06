# FastAPI + React WebSocket Chat

This repository contains two projects:

- `backend/` - FastAPI websocket server
- `frontend/` - React client (Vite)

## 1. Run backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 2. Run frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## 3. Test chat in two tabs

1. Open two browser tabs to `http://localhost:5173`.
2. Set a different name in each tab.
3. Send messages from either tab.
4. Both tabs should receive each message in real time.
