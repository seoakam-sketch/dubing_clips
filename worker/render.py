import os
import subprocess

from models.clip import Clip
from models.clip_candidate import ClipCandidate
from models.db import SessionLocal
from models.enums import ClipStatus
from worker.anthropic_client import call_claude, extract_json
from worker.celery_app import app
from worker.config import clip_dir
from worker.job_utils import job_run

BURN_IN_SUBTITLES = os.environ.get("BURN_IN_SUBTITLES", "true").lower() == "true"

# All three platforms currently converge on the same vertical H.264/AAC spec;
# kept as separate presets so a platform-specific bitrate/duration cap can be
# tuned independently later without touching the render call sites.
PLATFORM_PRESETS = {
    "instagram_reels": {"video_bitrate": "6M", "audio_bitrate": "192k"},
    "tiktok": {"video_bitrate": "6M", "audio_bitrate": "192k"},
    "youtube_shorts": {"video_bitrate": "8M", "audio_bitrate": "192k"},
}

CAPTION_SYSTEM_PROMPT = """You write short, punchy Persian social captions and \
relevant hashtags for a vertical short-form video clip, given its title and reason \
for being selected as a highlight. Respond with ONLY JSON: \
{"caption": "<1-2 sentence Persian caption>", "hashtags": ["#..."]}"""


def _escape_subtitle_path(path: str) -> str:
    # ffmpeg's subtitles filter treats ':' as an option separator, so on
    # Windows-style paths (and to be safe generally) escape it.
    return path.replace(":", "\\:")


@app.task(name="worker.render.render_final", bind=True, max_retries=1)
def render_final(self, clip_id: str) -> str:
    session = SessionLocal()
    try:
        clip = session.get(Clip, clip_id)
        if clip is None:
            raise ValueError(f"clip {clip_id} not found")
        candidate = session.get(ClipCandidate, clip.clip_candidate_id)

        try:
            with job_run("render", video_id=str(clip.video_id), clip_id=clip_id):
                work_dir = clip_dir(clip_id)
                outputs = {}

                for platform, preset in PLATFORM_PRESETS.items():
                    out_path = str(work_dir / f"final_{platform}.mp4")
                    vf = None
                    if BURN_IN_SUBTITLES and clip.subtitle_path:
                        vf = f"subtitles={_escape_subtitle_path(clip.subtitle_path)}"

                    cmd = ["ffmpeg", "-y", "-i", clip.cropped_path, "-i", clip.dubbed_path]
                    if vf:
                        cmd += ["-vf", vf]
                    cmd += [
                        "-map", "0:v:0", "-map", "1:a:0",
                        "-c:v", "libx264", "-b:v", preset["video_bitrate"],
                        "-c:a", "aac", "-b:a", preset["audio_bitrate"],
                        "-shortest", out_path,
                    ]
                    subprocess.run(cmd, check=True, capture_output=True)
                    outputs[platform] = out_path

                # Store the youtube_shorts render as the canonical final_output_path;
                # the other presets sit alongside it in the same clip directory.
                clip.final_output_path = outputs["youtube_shorts"]
                clip.status = ClipStatus.done.value
                session.commit()

                _write_caption_suggestion(candidate, work_dir)
        except Exception as exc:  # noqa: BLE001
            clip.status = ClipStatus.failed.value
            clip.error = str(exc)
            session.commit()
            raise

        return clip_id
    finally:
        session.close()


def _write_caption_suggestion(candidate: ClipCandidate, work_dir) -> None:
    # Caption/hashtag generation is a nice-to-have; never fail the render over it.
    try:
        raw = call_claude(
            CAPTION_SYSTEM_PROMPT,
            f"Title: {candidate.title_suggestion}\nReason selected: {candidate.reason}",
        )
        data = extract_json(raw)
        caption_text = data.get("caption", "") + "\n\n" + " ".join(data.get("hashtags", []))
        (work_dir / "caption_suggestion.txt").write_text(caption_text, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
