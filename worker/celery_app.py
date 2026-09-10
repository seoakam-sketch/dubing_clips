from celery import Celery

from worker.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

app = Celery(
    "clipdub",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        "worker.download",
        "worker.transcribe",
        "worker.highlight",
        "worker.clip",
        "worker.reframe",
        "worker.separate_audio",
        "worker.translate",
        "worker.dub",
        "worker.mix_audio",
        "worker.subtitle",
        "worker.render",
    ],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
)

# GPU-bound tasks (STT, Demucs, TTS, face-detection reframe) go on the "gpu"
# queue. The worker-gpu container MUST be started with `-c 1` so heavy tasks
# never run concurrently and blow out VRAM. Everything else runs on "cpu".
app.conf.task_routes = {
    "worker.transcribe.*": {"queue": "gpu"},
    "worker.reframe.*": {"queue": "gpu"},
    "worker.dub.*": {"queue": "gpu"},
    "worker.separate_audio.*": {"queue": "gpu"},
    "worker.download.*": {"queue": "cpu"},
    "worker.highlight.*": {"queue": "cpu"},
    "worker.clip.*": {"queue": "cpu"},
    "worker.translate.*": {"queue": "cpu"},
    "worker.subtitle.*": {"queue": "cpu"},
    "worker.render.*": {"queue": "cpu"},
    "worker.mix_audio.*": {"queue": "cpu"},
}
