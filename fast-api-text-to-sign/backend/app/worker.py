import time

from app.db import get_job, init_db, update_job
from app.renderers import get_renderer
from app.services import translate_text_to_sign_repr


def process_video_job(job_id: str) -> None:
    try:
        init_db()
        update_job(job_id, status="processing", progress=15)
        time.sleep(0.8)

        job = get_job(job_id)
        if not job:
            return

        sign_repr = translate_text_to_sign_repr(job["input_text"])
        update_job(
            job_id,
            progress=55,
            gloss=sign_repr.gloss,
            sign_repr_json=sign_repr.model_dump_json(),
        )
        time.sleep(1.0)

        renderer = get_renderer()
        result = renderer.render(sign_representation=sign_repr.model_dump(), job_id=job_id)
        update_job(job_id, status="done", progress=100, artifact_key=result.artifact_key)
    except Exception as exc:
        update_job(job_id, status="failed", progress=100, error=str(exc))
