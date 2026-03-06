from typing import Literal

from pydantic import BaseModel, Field


class SignToken(BaseModel):
    gloss: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)


class NonManualFeature(BaseModel):
    kind: Literal["eyebrow", "head", "mouth", "gaze"]
    value: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)


class SignRepresentation(BaseModel):
    language: str = "dgs"
    gloss: str
    tokens: list[SignToken]
    non_manual: list[NonManualFeature] = Field(default_factory=list)
    meta: dict[str, str] = Field(default_factory=dict)
