from models.clip import Clip
from models.clip_candidate import ClipCandidate
from models.db import SessionLocal
from models.enums import ClipStatus
from models.transcript import TranscriptSegment
from worker.celery_app import app
from worker.config import clip_dir
from worker.job_utils import job_run


def _srt_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _build_srt(segments, clip_start: float) -> str:
    lines = []
    for i, seg in enumerate(segments, start=1):
        start = max(seg.start - clip_start, 0)
        end = max(seg.end - clip_start, start + 0.1)
        text = seg.text_fa or seg.text_original
        lines.append(str(i))
        lines.append(f"{_srt_timestamp(start)} --> {_srt_timestamp(end)}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


@app.task(name="worker.subtitle.generate_subtitles", bind=True, max_retries=1)
def generate_subtitles(self, clip_id: str) -> str:
    session = SessionLocal()
    try:
        clip = session.get(Clip, clip_id)
        if clip is None:
            raise ValueError(f"clip {clip_id} not found")
        candidate = session.get(ClipCandidate, clip.clip_candidate_id)

        segments = (
            session.query(TranscriptSegment)
            .filter(
                TranscriptSegment.video_id == clip.video_id,
                TranscriptSegment.start >= candidate.start,
                TranscriptSegment.end <= candidate.end,
            )
            .order_by(TranscriptSegment.start)
            .all()
        )

        with job_run("subtitle", video_id=str(clip.video_id), clip_id=clip_id):
            srt_content = _build_srt(segments, candidate.start)
            srt_path = clip_dir(clip_id) / "subtitles_fa.srt"
            srt_path.write_text(srt_content, encoding="utf-8")

            clip.subtitle_path = str(srt_path)
            clip.status = ClipStatus.subtitling.value
            session.commit()

        return clip_id
    finally:
        session.close()
