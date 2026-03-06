from typing import Literal

from pydantic import BaseModel, Field


class SessionStart(BaseModel):
    type: Literal["session.start"]
    sessionId: str = Field(min_length=1)
    fps: int = Field(ge=1, le=60)
    language: str = "de"


class FrameChunk(BaseModel):
    type: Literal["frame.chunk"]
    sessionId: str = Field(min_length=1)
    seq: int = Field(ge=0)
    ts: float
    encoding: Literal["image/jpeg;base64"]
    payload: str = Field(min_length=1)


class CaptionResponse(BaseModel):
    type: Literal["caption.partial", "caption.final"]
    sessionId: str = Field(min_length=1)
    text: str
    confidence: float = Field(ge=0, le=1)
    isFinal: bool
    ts: float


class ErrorResponse(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str
    ts: float
