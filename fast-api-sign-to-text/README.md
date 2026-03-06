# Live Sign-to-Text Monorepo

Open-Source PoC fuer Live Sign-to-Text mit React + FastAPI + PyTorch.

## Struktur

- `frontend/`: React-App fuer Kameraaufnahme und Live-Captions
- `backend/`: FastAPI-Server fuer Frame-Streaming, Keypoint-Extraktion und Inference
- `ml/`: PyTorch-Sequenzmodell-Stub und austauschbare Inference-API
- `contracts/`: JSON-Contracts fuer Signaling, Frames und Caption-Responses

## Datenfluss

1. Frontend startet Kamera (`getUserMedia`) und verbindet WebSocket zum Backend.
2. Frontend sendet `session.start` und danach `frame.chunk` Nachrichten (Base64 JPEG).
3. Backend decodiert Frames, extrahiert MediaPipe Hand/Pose-Keypoints.
4. Keypoint-Sequenz wird durch ein austauschbares ML-Predictor-Interface in Text umgewandelt.
5. Backend sendet `caption.partial` / `caption.final` in Echtzeit zurueck.

## Start mit Docker

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- Health: http://localhost:8000/health

## Lokaler Start (ohne Docker)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

## Hinweise

- Der ML-Teil ist absichtlich ein Stub, aber ueber die Predictor-API austauschbar.
- Fuer produktive Nutzung: bessere Codec-Strategie (WebRTC/SRTP), Auth, Rate-Limits, GPU-Inference.

## Trainiertes Modell einbinden

1. Rohvideos in `ml/data/raw/<label>/` ablegen und Keypoints extrahieren:
   ```bash
   cd ml
   pip install -r requirements-extract.txt
   python extract_keypoints.py --input-dir data/raw --output-dir data/keypoints --frame-step 2
   ```
2. Modell trainieren:
   ```bash
   cd ml
   pip install -r requirements-train.txt
   python train.py --data-dir data/keypoints --output artifacts/sign_model.pt
   ```
3. Backend mit trainiertem Provider starten:
   ```bash
   cd backend
   MODEL_PROVIDER=trained MODEL_PATH=../ml/artifacts/sign_model.pt uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
