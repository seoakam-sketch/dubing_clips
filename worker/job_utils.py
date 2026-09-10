import logging
import time
import uuid
from contextlib import contextmanager

from models.db import SessionLocal
from models.enums import JobStatus
from models.job import Job

logger = logging.getLogger("clipdub.worker")


@contextmanager
def job_run(job_type: str, video_id: str | None = None, clip_id: str | None = None):
    """Tracks one Job row + logs timing for a pipeline stage.

    Each pipeline stage is wrapped in this context manager so a failure in one
    stage (e.g. dubbing a single clip) is recorded independently and never
    raises past the task boundary in a way that would abort sibling clips.
    """
    session = SessionLocal()
    job = Job(
        id=uuid.uuid4(),
        type=job_type,
        status=JobStatus.running.value,
        video_id=uuid.UUID(video_id) if video_id else None,
        clip_id=uuid.UUID(clip_id) if clip_id else None,
    )
    session.add(job)
    session.commit()

    started = time.monotonic()
    logger.info("job.start type=%s video_id=%s clip_id=%s", job_type, video_id, clip_id)
    try:
        yield job
        job.status = JobStatus.succeeded.value
        session.commit()
    except Exception as exc:  # noqa: BLE001 - deliberately broad: isolate stage failures
        job.status = JobStatus.failed.value
        job.error = str(exc)
        session.commit()
        logger.exception("job.failed type=%s video_id=%s clip_id=%s", job_type, video_id, clip_id)
        raise
    finally:
        elapsed = time.monotonic() - started
        logger.info(
            "job.end type=%s video_id=%s clip_id=%s status=%s elapsed=%.2fs",
            job_type,
            video_id,
            clip_id,
            job.status,
            elapsed,
        )
        session.close()
