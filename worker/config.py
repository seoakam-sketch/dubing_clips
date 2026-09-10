import os
from pathlib import Path

STORAGE_ROOT = Path(os.environ.get("STORAGE_ROOT", "./storage"))
VIDEOS_DIR = STORAGE_ROOT / "videos"
CLIPS_DIR = STORAGE_ROOT / "clips"
TMP_DIR = STORAGE_ROOT / "tmp"

for _dir in (VIDEOS_DIR, CLIPS_DIR, TMP_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "large-v3")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cuda")
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "float16")

TTS_ENGINE = os.environ.get("TTS_ENGINE", "piper")
PIPER_FA_VOICE_PATH = os.environ.get("PIPER_FA_VOICE_PATH", "")

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")


def video_dir(video_id: str) -> Path:
    d = VIDEOS_DIR / str(video_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def clip_dir(clip_id: str) -> Path:
    d = CLIPS_DIR / str(clip_id)
    d.mkdir(parents=True, exist_ok=True)
    return d
