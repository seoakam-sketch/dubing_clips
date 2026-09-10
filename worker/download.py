import subprocess

import yt_dlp

from models.db import SessionLocal
from models.enums import VideoStatus
from models.video import Video
from worker.celery_app import app
from worker.config import video_dir
from worker.job_utils import job_run


@app.task(name="worker.download.download_video", bind=True, max_retries=2)
def download_video(self, video_id: str) -> str:
    """Downloads the source video with yt-dlp and extracts a 16kHz mono WAV.

    Returns video_id so it can be chained straight into transcribe_video.
    """
    session = SessionLocal()
    try:
        video = session.get(Video, video_id)
        if video is None:
            raise ValueError(f"video {video_id} not found")

        video.status = VideoStatus.downloading.value
        session.commit()

        out_dir = video_dir(video_id)

        with job_run("download", video_id=video_id):
            ydl_opts = {
                "format": "bestvideo[height<=1080]+bestaudio/best",
                "outtmpl": str(out_dir / "source.%(ext)s"),
                "merge_output_format": "mp4",
                "noplaylist": True,
                "quiet": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video.source_url, download=True)
                downloaded_path = ydl.prepare_filename(info)
                if not downloaded_path.endswith(".mp4"):
                    downloaded_path = str(out_dir / "source.mp4")

            video.title = info.get("title")
            video.duration = info.get("duration")
            video.downloaded_path = downloaded_path
            video.video_metadata = {
                "description": info.get("description"),
                "thumbnail": info.get("thumbnail"),
                "uploader": info.get("uploader"),
            }
            session.commit()

            audio_path = str(out_dir / "audio.wav")
            with job_run("extract_audio", video_id=video_id):
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-i", downloaded_path,
                        "-ac", "1", "-ar", "16000", "-vn", audio_path,
                    ],
                    check=True,
                    capture_output=True,
                )
            video.audio_path = audio_path
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
