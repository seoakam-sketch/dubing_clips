import subprocess
import uuid

from models.clip import Clip
from models.clip_candidate import ClipCandidate
from models.db import SessionLocal
from models.enums import ClipStatus
from models.video import Video
from worker.celery_app import app
from worker.config import clip_dir
from worker.job_utils import job_run


@app.task(name="worker.clip.cut_clip", bind=True, max_retries=2)
def cut_clip(self, clip_candidate_id: str) -> str:
    """Cuts the approved segment out of the source video. Creates the Clip row
    and returns its id so the rest of the per-clip chain can pick it up.
    """
    session = SessionLocal()
    try:
        candidate = session.get(ClipCandidate, clip_candidate_id)
        if candidate is None:
            raise ValueError(f"clip candidate {clip_candidate_id} not found")
        video = session.get(Video, candidate.video_id)

        clip = Clip(
            id=uuid.uuid4(),
            clip_candidate_id=candidate.id,
            video_id=video.id,
            status=ClipStatus.cutting.value,
        )
        session.add(clip)
        session.commit()

        try:
            with job_run("clip", video_id=str(video.id), clip_id=str(clip.id)):
                out_dir = clip_dir(str(clip.id))
                out_path = str(out_dir / "cut.mp4")
                duration = candidate.end - candidate.start

                # Try a fast stream-copy cut first; fall back to re-encode if the
                # source's keyframe spacing makes a copy cut inaccurate/fail.
                copy_cmd = [
                    "ffmpeg", "-y", "-ss", str(candidate.start), "-i", video.downloaded_path,
                    "-t", str(duration), "-c", "copy", out_path,
                ]
                result = subprocess.run(copy_cmd, capture_output=True)
                if result.returncode != 0:
                    reencode_cmd = [
                        "ffmpeg", "-y", "-ss", str(candidate.start), "-i", video.downloaded_path,
                        "-t", str(duration), "-c:v", "libx264", "-c:a", "aac", out_path,
                    ]
                    subprocess.run(reencode_cmd, check=True, capture_output=True)

                clip.cropped_path = out_path
                session.commit()
        except Exception as exc:  # noqa: BLE001
            clip.status = ClipStatus.failed.value
            clip.error = str(exc)
            session.commit()
            raise

        return str(clip.id)
    finally:
        session.close()
