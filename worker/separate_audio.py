import shutil
import subprocess
from pathlib import Path

from models.clip import Clip
from models.db import SessionLocal
from worker.celery_app import app
from worker.config import clip_dir
from worker.job_utils import job_run

# Demucs writes to <out>/<model>/<track_name>/{vocals,no_vocals}.wav. We keep
# these two stems at fixed, well-known paths inside the clip's directory so
# worker.dub (vocals removed, dub replaces them) and worker.mix_audio
# (recombine dub + background) can find them by convention.
VOCALS_FILENAME = "vocals.wav"
BACKGROUND_FILENAME = "background.wav"


@app.task(name="worker.separate_audio.separate_audio", bind=True, max_retries=1)
def separate_audio(self, clip_id: str) -> str:
    session = SessionLocal()
    try:
        clip = session.get(Clip, clip_id)
        if clip is None:
            raise ValueError(f"clip {clip_id} not found")

        with job_run("separate_audio", video_id=str(clip.video_id), clip_id=clip_id):
            work_dir = clip_dir(clip_id)
            raw_audio = str(work_dir / "clip_audio.wav")
            subprocess.run(
                ["ffmpeg", "-y", "-i", clip.cropped_path, "-ac", "2", "-ar", "44100", raw_audio],
                check=True,
                capture_output=True,
            )

            demucs_out = work_dir / "demucs_out"
            subprocess.run(
                ["python", "-m", "demucs", "--two-stems", "vocals", "-o", str(demucs_out), raw_audio],
                check=True,
                capture_output=True,
            )

            # demucs default model dir name is "htdemucs"; track name matches
            # the input file's stem ("clip_audio").
            stem_dir = demucs_out / "htdemucs" / Path(raw_audio).stem
            shutil.copy(stem_dir / "vocals.wav", work_dir / VOCALS_FILENAME)
            shutil.copy(stem_dir / "no_vocals.wav", work_dir / BACKGROUND_FILENAME)
            shutil.rmtree(demucs_out, ignore_errors=True)

        return clip_id
    finally:
        session.close()
