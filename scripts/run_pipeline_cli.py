#!/usr/bin/env python3
"""Linear, no-Celery test of download -> extract audio -> transcribe.

Per the project spec, before wiring each stage into a Celery task we want a
plain script to validate the chain end-to-end on one sample video. Run it
directly (not through Docker Compose) with the same env vars the workers use.

Usage:
    python scripts/run_pipeline_cli.py "https://www.youtube.com/watch?v=..." \
        [--whisper-model tiny]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import yt_dlp


def download(url: str, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    ydl_opts = {
        "format": "bestvideo[height<=1080]+bestaudio/best",
        "outtmpl": str(out_dir / "source.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_path = ydl.prepare_filename(info)
        if not video_path.endswith(".mp4"):
            video_path = str(out_dir / "source.mp4")
    return {"video_path": video_path, "title": info.get("title"), "duration": info.get("duration")}


def extract_audio(video_path: str, out_dir: Path) -> str:
    audio_path = str(out_dir / "audio.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-ac", "1", "-ar", "16000", "-vn", audio_path],
        check=True,
    )
    return audio_path


def transcribe(audio_path: str, model_name: str) -> list[dict]:
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(audio_path, word_timestamps=True, vad_filter=True)
    return [
        {
            "start": seg.start,
            "end": seg.end,
            "text": seg.text.strip(),
            "words": [{"word": w.word, "start": w.start, "end": w.end} for w in (seg.words or [])],
        }
        for seg in segments
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--out-dir", default="./storage/tmp/cli_test")
    parser.add_argument(
        "--whisper-model",
        default="tiny",
        help="Use tiny/base/small for a quick CPU smoke test; large-v3 needs a GPU host.",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    print(f"[1/3] Downloading {args.url} ...", file=sys.stderr)
    meta = download(args.url, out_dir)
    print(json.dumps(meta, indent=2))

    print("[2/3] Extracting audio ...", file=sys.stderr)
    audio_path = extract_audio(meta["video_path"], out_dir)
    print(audio_path)

    print(f"[3/3] Transcribing with model={args.whisper_model} ...", file=sys.stderr)
    segments = transcribe(audio_path, args.whisper_model)
    transcript_path = out_dir / "transcript.json"
    transcript_path.write_text(json.dumps(segments, ensure_ascii=False, indent=2))
    print(f"Wrote {len(segments)} segments to {transcript_path}")


if __name__ == "__main__":
    main()
