from models.clip_candidate import ClipCandidate
from models.db import SessionLocal
from models.transcript import TranscriptSegment
from models.video import Video
from worker.anthropic_client import call_claude, extract_json
from worker.celery_app import app
from worker.job_utils import job_run

SYSTEM_PROMPT = """You select short, self-contained highlight clips from a video \
transcript for vertical short-form video (Reels/TikTok/Shorts). Pick moments that \
are emotionally engaging, funny, surprising, or make a complete standalone point \
without needing earlier context. Clips should be roughly 20-90 seconds long and \
must start and end on natural sentence boundaries from the given segments.

Respond with ONLY a JSON array, no prose, in this exact shape:
[
  {"start": <float seconds>, "end": <float seconds>, "score": <0-1 float>, \
"title": "<short catchy title>", "reason": "<one sentence why this works as a clip>"}
]
Return at most 8 candidates, ordered by score descending."""


@app.task(name="worker.highlight.detect_highlights", bind=True, max_retries=2)
def detect_highlights(self, video_id: str) -> str:
    session = SessionLocal()
    try:
        video = session.get(Video, video_id)
        if video is None:
            raise ValueError(f"video {video_id} not found")

        segments = (
            session.query(TranscriptSegment)
            .filter(TranscriptSegment.video_id == video.id)
            .order_by(TranscriptSegment.start)
            .all()
        )

        with job_run("highlight", video_id=video_id):
            transcript_text = "\n".join(
                f"[{s.start:.2f}-{s.end:.2f}] {s.text_original}" for s in segments
            )
            user_prompt = (
                f"Video title: {video.title or '(unknown)'}\n\n"
                f"Transcript with timestamps:\n{transcript_text}"
            )
            raw = call_claude(SYSTEM_PROMPT, user_prompt)
            candidates = extract_json(raw)

            session.query(ClipCandidate).filter(ClipCandidate.video_id == video.id).delete()
            for c in candidates:
                session.add(
                    ClipCandidate(
                        video_id=video.id,
                        start=float(c["start"]),
                        end=float(c["end"]),
                        score=float(c.get("score", 0)),
                        title_suggestion=c.get("title"),
                        reason=c.get("reason"),
                    )
                )
            session.commit()

        return video_id
    finally:
        session.close()
