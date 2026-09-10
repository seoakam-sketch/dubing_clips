import subprocess
from pathlib import Path

from models.clip import Clip
from models.clip_candidate import ClipCandidate
from models.db import SessionLocal
from models.enums import ClipStatus
from models.transcript import TranscriptSegment
from worker.celery_app import app
from worker.cleanup import remove_paths
from worker.config import PIPER_FA_VOICE_PATH, TTS_ENGINE, clip_dir
from worker.job_utils import job_run
from worker.tts_engines import get_engine


def _time_stretch(src_path: str, target_duration: float, out_path: str) -> None:
    """Stretches/compresses src_path to target_duration using ffmpeg's atempo,
    which only accepts factors in [0.5, 2.0] - chain filters for extremes.
    """
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", src_path,
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    src_duration = float(probe) if probe else target_duration
    if src_duration <= 0:
        src_duration = target_duration

    factor = src_duration / target_duration
    filters = []
    remaining = factor
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    filters.append(f"atempo={remaining:.4f}")

    subprocess.run(
        ["ffmpeg", "-y", "-i", src_path, "-filter:a", ",".join(filters), out_path],
        check=True,
        capture_output=True,
    )


@app.task(name="worker.dub.synthesize_dub", bind=True, max_retries=1)
def synthesize_dub(self, clip_id: str) -> str:
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
                TranscriptSegment.text_fa.isnot(None),
            )
            .order_by(TranscriptSegment.start)
            .all()
        )

        try:
            with job_run("dub", video_id=str(clip.video_id), clip_id=clip_id):
                engine = get_engine(TTS_ENGINE, voice_path=PIPER_FA_VOICE_PATH)
                work_dir = clip_dir(clip_id)
                pieces_dir = work_dir / "dub_pieces"
                pieces_dir.mkdir(exist_ok=True)

                dubbed_track = str(work_dir / "vocals.wav")  # overwrite the extracted vocals stem
                concat_lines = []

                for i, seg in enumerate(segments):
                    raw_path = str(pieces_dir / f"{i}_raw.wav")
                    engine.synthesize(seg.text_fa, raw_path)

                    stretched_path = str(pieces_dir / f"{i}_stretched.wav")
                    seg_duration = max(seg.end - seg.start, 0.3)
                    _time_stretch(raw_path, seg_duration, stretched_path)
                    concat_lines.append(f"file '{Path(stretched_path).name}'")

                (pieces_dir / "concat.txt").write_text("\n".join(concat_lines))
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                        "-i", str(pieces_dir / "concat.txt"), "-c", "copy", dubbed_track,
                    ],
                    check=True,
                    capture_output=True,
                    cwd=str(pieces_dir),
                )

                clip.dubbed_path = dubbed_track
                clip.status = ClipStatus.dubbing.value
                session.commit()
                remove_paths(pieces_dir)
        except Exception as exc:  # noqa: BLE001
            clip.status = ClipStatus.failed.value
            clip.error = str(exc)
            session.commit()
            raise

        return clip_id
    finally:
        session.close()
