import subprocess

from models.clip import Clip
from models.db import SessionLocal
from worker.celery_app import app
from worker.config import clip_dir
from worker.job_utils import job_run
from worker.separate_audio import BACKGROUND_FILENAME


@app.task(name="worker.mix_audio.mix_audio", bind=True, max_retries=1)
def mix_audio(self, clip_id: str) -> str:
    session = SessionLocal()
    try:
        clip = session.get(Clip, clip_id)
        if clip is None:
            raise ValueError(f"clip {clip_id} not found")

        with job_run("mix_audio", video_id=str(clip.video_id), clip_id=clip_id):
            work_dir = clip_dir(clip_id)
            background_path = work_dir / BACKGROUND_FILENAME
            mixed_path = str(work_dir / "mixed.wav")

            if background_path.exists():
                subprocess.run(
                    [
                        "ffmpeg", "-y",
                        "-i", clip.dubbed_path,
                        "-i", str(background_path),
                        "-filter_complex", "[0:a]volume=1.0[a0];[1:a]volume=0.5[a1];[a0][a1]amix=inputs=2:duration=longest",
                        mixed_path,
                    ],
                    check=True,
                    capture_output=True,
                )
            else:
                # No background stem (e.g. Demucs was skipped/failed upstream) -
                # fall back to the dubbed voice track alone rather than failing.
                subprocess.run(
                    ["ffmpeg", "-y", "-i", clip.dubbed_path, mixed_path],
                    check=True,
                    capture_output=True,
                )

            clip.dubbed_path = mixed_path
            session.commit()

        return clip_id
    finally:
        session.close()
