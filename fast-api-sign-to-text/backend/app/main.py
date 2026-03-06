from __future__ import annotations

import base64
import time
from collections import deque

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from .contracts import CaptionResponse, ErrorResponse, FrameChunk, SessionStart
from .inference_client import InferenceClient
from .keypoints import FEATURE_SIZE, KeypointExtractor

SEQUENCE_LENGTH = 32

app = FastAPI(title="Live Sign-to-Text API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def decode_frame(payload_b64: str) -> np.ndarray | None:
    try:
        raw = base64.b64decode(payload_b64)
        arr = np.frombuffer(raw, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return frame
    except Exception:
        return None


@app.websocket("/ws/live")
async def websocket_live(ws: WebSocket) -> None:
    await ws.accept()

    extractor = KeypointExtractor()
    inference = InferenceClient()
    session_id = ""
    buffer: deque[np.ndarray] = deque(maxlen=SEQUENCE_LENGTH)

    try:
        while True:
            msg = await ws.receive_json()
            msg_type = msg.get("type")

            if msg_type == "session.start":
                try:
                    start = SessionStart.model_validate(msg)
                    session_id = start.sessionId
                    await ws.send_json({
                        "type": "session.ack",
                        "sessionId": session_id,
                        "ts": time.time(),
                    })
                except ValidationError as exc:
                    err = ErrorResponse(
                        code="invalid_session_start",
                        message=str(exc),
                        ts=time.time(),
                    )
                    await ws.send_json(err.model_dump())
                continue

            if msg_type != "frame.chunk":
                err = ErrorResponse(
                    code="unsupported_type",
                    message=f"Unsupported message type: {msg_type}",
                    ts=time.time(),
                )
                await ws.send_json(err.model_dump())
                continue

            try:
                frame_msg = FrameChunk.model_validate(msg)
            except ValidationError as exc:
                err = ErrorResponse(
                    code="invalid_frame_chunk",
                    message=str(exc),
                    ts=time.time(),
                )
                await ws.send_json(err.model_dump())
                continue

            frame = decode_frame(frame_msg.payload)
            if frame is None:
                err = ErrorResponse(
                    code="decode_error",
                    message="Could not decode JPEG frame",
                    ts=time.time(),
                )
                await ws.send_json(err.model_dump())
                continue

            keypoints = extractor.extract(frame).vector
            if keypoints.shape[0] != FEATURE_SIZE:
                err = ErrorResponse(
                    code="feature_size_mismatch",
                    message="Unexpected keypoint vector size",
                    ts=time.time(),
                )
                await ws.send_json(err.model_dump())
                continue

            buffer.append(keypoints)
            if len(buffer) < SEQUENCE_LENGTH:
                continue

            sequence = np.stack(buffer, axis=0)
            text, confidence, is_final = inference.infer(sequence)
            response = CaptionResponse(
                type="caption.final" if is_final else "caption.partial",
                sessionId=frame_msg.sessionId,
                text=text,
                confidence=confidence,
                isFinal=is_final,
                ts=time.time(),
            )
            await ws.send_json(response.model_dump())

    except WebSocketDisconnect:
        return
