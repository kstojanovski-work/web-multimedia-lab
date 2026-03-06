import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
STATIC_DIR = BACKEND_DIR / "static"
DB_PATH = Path(os.getenv("JOBS_DB_PATH", DATA_DIR / "jobs.db"))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
RQ_QUEUE_NAME = os.getenv("RQ_QUEUE_NAME", "video_jobs")
ARTIFACT_SIGNING_SECRET = os.getenv("ARTIFACT_SIGNING_SECRET", "dev-only-change-me")
ARTIFACT_URL_TTL_SECONDS = int(os.getenv("ARTIFACT_URL_TTL_SECONDS", "900"))
