from models.clip import Clip
from models.clip_candidate import ClipCandidate
from models.db import SessionLocal
from models.enums import ClipStatus
from models.transcript import TranscriptSegment
from worker.anthropic_client import call_claude, extract_json
from worker.celery_app import app
from worker.job_utils import job_run

SYSTEM_PROMPT = """You translate English (or the transcript's source language) video \
subtitle segments into natural, spoken Persian (Farsi) suitable for dubbing. Keep each \
translation close in spoken duration to the original so it can be dubbed and time-stretched \
without excessive speed-up. Preserve tone (casual/formal) and any humor or emphasis.

Input is a JSON array of {"id": <string>, "text": <string>}.
Respond with ONLY a JSON array of {"id": <string>, "text_fa": <string>}, same length and ids, \
no prose."""


@app.task(name="worker.translate.translate_segment", bind=True, max_retries=2)
def translate_segment(self, clip_id: str) -> str:
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

        if not segments:
            return clip_id

        with job_run("translate", video_id=str(clip.video_id), clip_id=clip_id):
            payload = [{"id": str(s.id), "text": s.text_original} for s in segments]
            raw = call_claude(SYSTEM_PROMPT, str(payload))
            translations = {t["id"]: t["text_fa"] for t in extract_json(raw)}

            by_id = {str(s.id): s for s in segments}
            for seg_id, text_fa in translations.items():
                if seg_id in by_id:
                    by_id[seg_id].text_fa = text_fa
            clip.status = ClipStatus.translating.value
            session.commit()

        return clip_id
    finally:
        session.close()
