import hashlib
import hmac
from pathlib import Path
from urllib.parse import quote

from app.settings import ARTIFACT_SIGNING_SECRET, ARTIFACT_URL_TTL_SECONDS, STATIC_DIR


class LocalArtifactStorage:
    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = (root_dir or STATIC_DIR).resolve()

    def create_signed_url(self, artifact_key: str, ttl_seconds: int | None = None) -> str:
        ttl = ttl_seconds or ARTIFACT_URL_TTL_SECONDS
        expires_at = self._now_epoch() + ttl
        signature = self._sign(artifact_key=artifact_key, expires_at=expires_at)
        encoded_key = quote(artifact_key, safe="/")
        return f"/api/artifacts/{encoded_key}?exp={expires_at}&sig={signature}"

    def verify_signature(self, artifact_key: str, expires_at: int, signature: str) -> bool:
        if expires_at < self._now_epoch():
            return False
        expected = self._sign(artifact_key=artifact_key, expires_at=expires_at)
        return hmac.compare_digest(expected, signature)

    def resolve_path(self, artifact_key: str) -> Path:
        candidate = (self.root_dir / artifact_key).resolve()
        if self.root_dir not in candidate.parents and candidate != self.root_dir:
            raise ValueError("Artifact path escapes storage root")
        if not candidate.exists() or not candidate.is_file():
            raise FileNotFoundError("Artifact not found")
        return candidate

    def _sign(self, artifact_key: str, expires_at: int) -> str:
        payload = f"{artifact_key}:{expires_at}".encode("utf-8")
        return hmac.new(ARTIFACT_SIGNING_SECRET.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    @staticmethod
    def _now_epoch() -> int:
        from time import time

        return int(time())


def get_artifact_storage() -> LocalArtifactStorage:
    return LocalArtifactStorage()
