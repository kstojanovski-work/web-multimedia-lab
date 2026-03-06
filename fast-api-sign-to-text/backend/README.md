# Backend (FastAPI)

## Features

- WebSocket Endpoint: `ws://<host>:8000/ws/live`
- Healthcheck: `GET /health`
- MediaPipe Pose+Hands Keypoint-Extraktion
- Austauschbare ML-Inference ueber `ml/sign2text/inference.py`

## Laufzeit-Konfiguration

- `MODEL_PROVIDER=stub`
- `MODEL_PROVIDER=trained` (mit Checkpoint)
- `MODEL_PATH=/app/ml/artifacts/sign_model.pt`

## Message-Typen

- inbound: `session.start`, `frame.chunk`
- outbound: `session.ack`, `caption.partial`, `caption.final`, `error`
