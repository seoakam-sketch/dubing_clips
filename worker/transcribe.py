from models.db import SessionLocal
from models.enums import VideoStatus
from models.transcript import TranscriptSegment
from models.video import Video
from worker.celery_app import app
from worker.config import WHISPER_COMPUTE_TYPE, WHISPER_DEVICE, WHISPER_MODEL
from worker.job_utils import job_run

_model = None


def _get_model():
    # Lazy singleton: loading a faster-whisper model (esp. large-v3) is
    # expensive; the gpu worker runs with concurrency=1 so one load per
    # process is enough and avoids re-loading it for every clip's video.
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        _model = WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE)
    return _model


@app.task(name="worker.transcribe.transcribe_video", bind=True, max_retries=1)
def transcribe_video(self, video_id: str) -> str:
    session = SessionLocal()
    try:
        video = session.get(Video, video_id)
        if video is None:
            raise ValueError(f"video {video_id} not found")

        video.status = VideoStatus.transcribing.value
        session.commit()

        with job_run("transcribe", video_id=video_id):
            model = _get_model()
            segments, _info = model.transcribe(
                video.audio_path, word_timestamps=True, vad_filter=True
            )

            session.query(TranscriptSegment).filter(
                TranscriptSegment.video_id == video.id
            ).delete()

            for seg in segments:
                words = [
                    {"word": w.word, "start": w.start, "end": w.end}
                    for w in (seg.words or [])
                ]
                session.add(
                    TranscriptSegment(
                        video_id=video.id,
                        start=seg.start,
                        end=seg.end,
                        text_original=seg.text.strip(),
                        words=words,
                    )
                )
            video.status = VideoStatus.ready.value
            session.commit()

        return video_id
    except Exception as exc:  # noqa: BLE001
        video = session.get(Video, video_id)
        if video:
            video.status = VideoStatus.failed.value
            video.error = str(exc)
            session.commit()
        raise
    finally:
        session.close()
