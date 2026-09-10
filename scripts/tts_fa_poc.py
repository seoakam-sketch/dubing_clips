#!/usr/bin/env python3
"""Proof-of-concept: evaluate open-source TTS quality for Persian dubbing.

This is the project's main technical risk (see the spec): XTTS v2 does not
officially list Persian in its supported languages, and Piper's quality
depends entirely on which community Persian voice checkpoint is used. This
script is written so it can run standalone, but it downloads large models
and (for XTTS) benefits heavily from a GPU - run it on your GPU-equipped
machine, NOT in a constrained/CPU-only sandbox.

What it does:
  1. Synthesizes a fixed set of Persian test sentences with Piper (if a
     voice model path is given).
  2. Synthesizes the same sentences with XTTS v2 forcing language="fa" (if
     --try-xtts is passed) - this may simply fail or produce garbage since
     Persian isn't an officially supported XTTS language; that failure mode
     itself is useful data for deciding whether to pursue a fine-tune.
  3. Writes all outputs to ./scripts/tts_poc_output/ for manual listening
     and scoring.

Usage:
    python scripts/tts_fa_poc.py --piper-voice /path/to/fa_IR-voice.onnx
    python scripts/tts_fa_poc.py --piper-voice /path/to/voice.onnx --try-xtts

Evaluation checklist (fill in manually after listening):
  - Intelligibility: are words/phonemes correct?
  - Naturalness: does it sound robotic / does prosody make sense?
  - Pronunciation: are Persian-specific sounds (خ، ق، ع) rendered correctly?
  - Speed/pacing: usable for dubbing without extreme time-stretching?
Record results in a short note next to this script so future runs on new
voices/checkpoints can be compared.
"""
import argparse
from pathlib import Path

TEST_SENTENCES = [
    "سلام، امروز حالت چطوره؟",
    "این یکی از جالب‌ترین لحظات این ویدیوئه.",
    "من واقعاً نمی‌تونم باور کنم که این اتفاق افتاد!",
    "بذار بهت بگم چرا این موضوع اینقدر مهمه.",
    "ممنون که تا اینجای ویدیو رو تماشا کردید.",
]

OUTPUT_DIR = Path(__file__).parent / "tts_poc_output"


def run_piper(voice_path: str) -> None:
    import subprocess

    out_dir = OUTPUT_DIR / "piper"
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, text in enumerate(TEST_SENTENCES):
        out_path = out_dir / f"{i:02d}.wav"
        print(f"[piper] synthesizing sentence {i}: {text}")
        subprocess.run(
            ["piper", "--model", voice_path, "--output_file", str(out_path)],
            input=text.encode("utf-8"),
            check=True,
        )
    print(f"Piper outputs written to {out_dir}")


def run_xtts() -> None:
    from TTS.api import TTS

    out_dir = OUTPUT_DIR / "xtts"
    out_dir.mkdir(parents=True, exist_ok=True)
    print("[xtts] loading tts_models/multilingual/multi-dataset/xtts_v2 ...")
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")

    for i, text in enumerate(TEST_SENTENCES):
        out_path = out_dir / f"{i:02d}.wav"
        print(f"[xtts] synthesizing sentence {i} with language='fa' (unsupported - expect possible failure): {text}")
        try:
            tts.tts_to_file(text=text, language="fa", file_path=str(out_path))
        except Exception as exc:  # noqa: BLE001 - we want to record and continue, not crash the POC
            print(f"[xtts] FAILED on sentence {i}: {exc}")
    print(f"XTTS outputs (where successful) written to {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--piper-voice", help="Path to a Piper Persian .onnx voice model")
    parser.add_argument(
        "--try-xtts", action="store_true",
        help="Also attempt XTTS v2 with language='fa' (unsupported; for research only)",
    )
    args = parser.parse_args()

    if not args.piper_voice and not args.try_xtts:
        parser.error("pass --piper-voice and/or --try-xtts")

    if args.piper_voice:
        run_piper(args.piper_voice)
    if args.try_xtts:
        run_xtts()


if __name__ == "__main__":
    main()
