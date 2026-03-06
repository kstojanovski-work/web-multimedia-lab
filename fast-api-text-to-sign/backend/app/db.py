import sqlite3
from typing import Any

from app.services import utc_now_iso
from app.settings import DB_PATH


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS video_jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                progress INTEGER NOT NULL,
                input_text TEXT NOT NULL,
                gloss TEXT,
                sign_repr_json TEXT,
                artifact_key TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(video_jobs)").fetchall()
        }
        if "artifact_key" not in columns:
            conn.execute("ALTER TABLE video_jobs ADD COLUMN artifact_key TEXT")
            # Legacy compatibility: keep existing values from old schema if present.
            if "video_url" in columns:
                conn.execute("UPDATE video_jobs SET artifact_key = video_url WHERE artifact_key IS NULL")
        if "sign_repr_json" not in columns:
            conn.execute("ALTER TABLE video_jobs ADD COLUMN sign_repr_json TEXT")
        conn.commit()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "job_id": row["job_id"],
        "status": row["status"],
        "progress": row["progress"],
        "input_text": row["input_text"],
        "gloss": row["gloss"],
        "sign_repr_json": row["sign_repr_json"],
        "artifact_key": row["artifact_key"],
        "error": row["error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_job(job_id: str, input_text: str) -> dict[str, Any]:
    now = utc_now_iso()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO video_jobs (job_id, status, progress, input_text, gloss, sign_repr_json, artifact_key, error, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (job_id, "queued", 0, input_text, None, None, None, None, now, now),
        )
        conn.commit()

    record = get_job(job_id)
    if not record:
        raise RuntimeError("Could not load created job")
    return record


def get_job(job_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM video_jobs WHERE job_id = ?", (job_id,)).fetchone()
    return _row_to_dict(row) if row else None


def update_job(job_id: str, **updates: Any) -> dict[str, Any] | None:
    if not updates:
        return get_job(job_id)

    updates = {**updates, "updated_at": utc_now_iso()}
    columns = ", ".join(f"{key} = ?" for key in updates.keys())
    values = list(updates.values()) + [job_id]

    with _connect() as conn:
        conn.execute(f"UPDATE video_jobs SET {columns} WHERE job_id = ?", values)
        conn.commit()

    return get_job(job_id)
