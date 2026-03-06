import asyncio
import json
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.db import create_job, get_job, init_db, update_job
from app.queue import get_queue
from app.services import translate_text_to_sign_repr
from app.settings import STATIC_DIR
from app.storage import get_artifact_storage

app = FastAPI(title="Text-to-Sign API", version="0.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    output_mode: Literal["gloss", "video"] = "gloss"


class TranslateResponse(BaseModel):
    input_text: str
    gloss: str
    output_mode: Literal["gloss", "video"]
    sign_representation: dict | None = None
    video_url: str | None = None


class VideoJobCreateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class VideoJobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "processing", "done", "failed"]
    progress: int = Field(ge=0, le=100)
    input_text: str
    gloss: str | None = None
    sign_representation: dict | None = None
    artifact_key: str | None = None
    video_url: str | None = None
    error: str | None = None
    created_at: str
    updated_at: str


def build_video_url(artifact_key: str | None) -> str | None:
    if not artifact_key:
        return None
    storage = get_artifact_storage()
    return storage.create_signed_url(artifact_key)


def serialize_job(job_record: dict) -> VideoJobStatus:
    sign_repr = None
    if job_record.get("sign_repr_json"):
        try:
            sign_repr = json.loads(job_record["sign_repr_json"])
        except json.JSONDecodeError:
            sign_repr = None

    return VideoJobStatus(
        job_id=job_record["job_id"],
        status=job_record["status"],
        progress=job_record["progress"],
        input_text=job_record["input_text"],
        gloss=job_record["gloss"],
        sign_representation=sign_repr,
        artifact_key=job_record.get("artifact_key"),
        video_url=build_video_url(job_record.get("artifact_key")),
        error=job_record["error"],
        created_at=job_record["created_at"],
        updated_at=job_record["updated_at"],
    )


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    STATIC_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/translate", response_model=TranslateResponse)
def translate(payload: TranslateRequest) -> TranslateResponse:
    sign_repr = translate_text_to_sign_repr(payload.text)
    gloss = sign_repr.gloss
    video_url = None

    if payload.output_mode == "video":
        video_url = build_video_url("videos/demo.mp4")

    return TranslateResponse(
        input_text=payload.text,
        gloss=gloss,
        output_mode=payload.output_mode,
        sign_representation=sign_repr.model_dump(),
        video_url=video_url,
    )


@app.post("/api/jobs", response_model=VideoJobStatus)
def create_video_job(payload: VideoJobCreateRequest) -> VideoJobStatus:
    job_id = str(uuid4())
    created = create_job(job_id=job_id, input_text=payload.text)

    try:
        queue = get_queue()
        queue.enqueue("app.worker.process_video_job", job_id, job_timeout=300)
    except Exception as exc:
        failed = update_job(job_id, status="failed", progress=100, error=f"Queue enqueue failed: {exc}")
        if not failed:
            raise HTTPException(status_code=500, detail="Could not update failed job state") from exc
        return serialize_job(failed)

    return serialize_job(created)


@app.get("/api/jobs/{job_id}", response_model=VideoJobStatus)
def get_video_job(job_id: str) -> VideoJobStatus:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return serialize_job(job)


@app.get("/api/artifacts/{artifact_key:path}")
def get_signed_artifact(artifact_key: str, exp: int = Query(...), sig: str = Query(...)) -> FileResponse:
    storage = get_artifact_storage()
    if not storage.verify_signature(artifact_key=artifact_key, expires_at=exp, signature=sig):
        raise HTTPException(status_code=403, detail="Invalid or expired artifact URL")

    try:
        path = storage.resolve_path(artifact_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FileResponse(path)


@app.websocket("/ws/translate")
async def ws_translate(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            text = await websocket.receive_text()
            sign_repr = translate_text_to_sign_repr(text)
            await websocket.send_json(
                {
                    "type": "translation",
                    "input_text": text,
                    "gloss": sign_repr.gloss,
                    "sign_representation": sign_repr.model_dump(),
                }
            )
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/jobs/{job_id}")
async def ws_job_updates(websocket: WebSocket, job_id: str) -> None:
    await websocket.accept()

    exists = get_job(job_id)
    if not exists:
        await websocket.send_json({"type": "error", "message": "Job not found", "job_id": job_id})
        await websocket.close(code=1008)
        return

    last_sent_signature: tuple[str, int] | None = None

    try:
        while True:
            job = get_job(job_id)
            if not job:
                await websocket.send_json({"type": "error", "message": "Job not found", "job_id": job_id})
                await websocket.close(code=1008)
                return

            signature = (job["status"], job["progress"])
            if signature != last_sent_signature:
                payload = serialize_job(job).model_dump()
                await websocket.send_json({"type": "job_update", **payload})
                last_sent_signature = signature

            if job["status"] in {"done", "failed"}:
                await websocket.close(code=1000)
                return

            await asyncio.sleep(0.4)
    except WebSocketDisconnect:
        pass
