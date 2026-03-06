# Text-to-Sign: React + FastAPI

Dieses Repository enthaelt ein Grundgeruest fuer:
- `frontend/`: React (Vite) fuer Texteingabe und Darstellung
- `backend/`: FastAPI API-Layer + persistente Video-Jobs (SQLite) + Queue (Redis/RQ)

## Architektur (aktuell)

- `POST /api/translate`: synchroner Quick-Flow (Gloss oder Demo-Video-URL)
- `POST /api/jobs`: erstellt asynchronen Video-Job
- `GET /api/jobs/{job_id}`: liefert Job-Status aus SQLite
- `WS /ws/jobs/{job_id}`: streamt Job-Statusaenderungen
- `GET /api/artifacts/{artifact_key}?exp=...&sig=...`: liefert signierte Video-Artefakte
- RQ-Worker verarbeitet Jobs aus Redis-Queue `video_jobs`
- Job-Status wird in `backend/data/jobs.db` persistiert
- Pipeline ist explizit: `text -> sign_representation -> renderer -> artifact`

## 1) Redis starten

Mit Docker Compose:

```bash
docker compose up -d redis
```

## 2) Backend starten

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 3) Worker starten (separates Terminal)

```bash
cd backend
source .venv/bin/activate
rq worker video_jobs --url redis://localhost:6379/0
```

## 4) Frontend starten

```bash
cd frontend
npm install
npm run dev
```

Frontend: `http://localhost:5173`

## API-Endpunkte

- `GET  http://localhost:8000/health`
- `POST http://localhost:8000/api/translate`
- `POST http://localhost:8000/api/jobs`
- `GET  http://localhost:8000/api/jobs/{job_id}`
- `WS   ws://localhost:8000/ws/jobs/{job_id}`
- `WS   ws://localhost:8000/ws/translate`
- `GET  http://localhost:8000/api/artifacts/{artifact_key}?exp=...&sig=...`

## Beispiel Video-Job

Request:

```json
{
  "text": "Guten Tag, wie kann ich helfen?"
}
```

Response (initial):

```json
{
  "job_id": "f7f50322-6e25-4cb7-b708-5a2df5e8ca6a",
  "status": "queued",
  "progress": 0,
  "input_text": "Guten Tag, wie kann ich helfen?",
  "gloss": null,
  "sign_representation": null,
  "artifact_key": null,
  "video_url": null,
  "error": null,
  "created_at": "2026-02-27T17:00:00+00:00",
  "updated_at": "2026-02-27T17:00:00+00:00"
}
```

Final (done):

```json
{
  "status": "done",
  "progress": 100,
  "sign_representation": {
    "language": "dgs",
    "gloss": "GUTEN TAG WIE KANN ICH HELFEN",
    "tokens": [
      {"gloss": "GUTEN", "start_ms": 0, "end_ms": 420}
    ],
    "non_manual": [
      {"kind": "eyebrow", "value": "neutral", "start_ms": 0, "end_ms": 2520}
    ],
    "meta": {"generator": "demo-rule-based-v1"}
  },
  "artifact_key": "videos/demo.mp4",
  "video_url": "/api/artifacts/videos/demo.mp4?exp=1700000000&sig=..."
}
```

## Konfiguration (optional)

- `REDIS_URL` (default: `redis://localhost:6379/0`)
- `RQ_QUEUE_NAME` (default: `video_jobs`)
- `JOBS_DB_PATH` (default: `backend/data/jobs.db`)
- `ARTIFACT_SIGNING_SECRET` (default: `dev-only-change-me`)
- `ARTIFACT_URL_TTL_SECONDS` (default: `900`)
- `VITE_API_BASE` (Frontend, default: `http://localhost:8000`)

## Hinweise

- Video-Rendering ist aktuell ein Stub-Worker und liefert Demo-MP4.
- Die Jobdaten bleiben bei API-Neustart erhalten (SQLite).
- Redis muss laufen, damit neue Jobs von der API in die Queue gestellt werden koennen.
- In Produktion solltest du `ARTIFACT_SIGNING_SECRET` unbedingt setzen.
