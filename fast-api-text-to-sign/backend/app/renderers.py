from dataclasses import dataclass
from typing import Protocol


@dataclass
class RenderResult:
    artifact_key: str


class VideoRenderer(Protocol):
    def render(self, sign_representation: dict, job_id: str) -> RenderResult:
        ...


class DemoVideoRenderer:
    def __init__(self, demo_artifact_key: str = "videos/demo.mp4") -> None:
        self.demo_artifact_key = demo_artifact_key

    def render(self, sign_representation: dict, job_id: str) -> RenderResult:
        # Stub renderer. Replace with model + avatar rendering pipeline.
        return RenderResult(artifact_key=self.demo_artifact_key)


def get_renderer() -> VideoRenderer:
    return DemoVideoRenderer()
