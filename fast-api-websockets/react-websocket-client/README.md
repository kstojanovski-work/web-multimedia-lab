# React WebSocket Client

Minimal React app that connects to the FastAPI WebSocket endpoint from `../fastapi-websocket-project`.

## Setup

```bash
cd react-websocket-client
npm install
```

## Run frontend

```bash
npm run dev
```

The app runs on `http://localhost:5173` by default.

## Run backend (separate terminal)

```bash
cd fastapi-websocket-project
uvicorn app.main:app --reload
```

By default, the frontend connects to:

`ws://localhost:8000/ws/{client_id}`
