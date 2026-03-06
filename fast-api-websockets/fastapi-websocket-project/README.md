# FastAPI WebSocket Project

A minimal FastAPI project that includes:
- HTTP health endpoint (`GET /health`)
- WebSocket endpoint (`/ws/{client_id}`)
- Pytest tests for WebSocket communication

## Setup

```bash
cd fastapi-websocket-project
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Run the app

```bash
uvicorn app.main:app --reload
```

## Run tests

```bash
pytest
```
