"""Pluggable Persian TTS engines.

Which engine is production-ready for Persian is an open technical risk (see
scripts/tts_fa_poc.py): XTTS v2 does not officially list Persian among its
supported languages, and Piper's quality depends entirely on which community
Persian voice is used. Both are implemented behind the same TTSEngine
interface so worker.dub can switch via the TTS_ENGINE env var without code
changes once the POC picks a winner.
"""
from abc import ABC, abstractmethod


class TTSEngine(ABC):
    @abstractmethod
    def synthesize(self, text: str, out_path: str) -> str:
        """Synthesizes `text` (Persian) to a WAV file at out_path. Returns out_path."""


class PiperEngine(TTSEngine):
    def __init__(self, voice_path: str):
        if not voice_path:
            raise ValueError("PIPER_FA_VOICE_PATH is not set")
        self.voice_path = voice_path

    def synthesize(self, text: str, out_path: str) -> str:
        import subprocess

        subprocess.run(
            ["piper", "--model", self.voice_path, "--output_file", out_path],
            input=text.encode("utf-8"),
            check=True,
            capture_output=True,
        )
        return out_path


class XTTSEngine(TTSEngine):
    """Requires a Persian-capable checkpoint/fine-tune; the stock XTTS v2
    release does not officially support Persian. See scripts/tts_fa_poc.py.
    """

    _model = None

    def __init__(self, speaker_wav: str | None = None):
        self.speaker_wav = speaker_wav

    def _get_model(self):
        if XTTSEngine._model is None:
            from TTS.api import TTS

            XTTSEngine._model = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
        return XTTSEngine._model

    def synthesize(self, text: str, out_path: str) -> str:
        model = self._get_model()
        model.tts_to_file(
            text=text,
            speaker_wav=self.speaker_wav,
            language="fa",
            file_path=out_path,
        )
        return out_path


def get_engine(name: str, **kwargs) -> TTSEngine:
    if name == "piper":
        return PiperEngine(kwargs.get("voice_path", ""))
    if name == "xtts":
        return XTTSEngine(kwargs.get("speaker_wav"))
    raise ValueError(f"unknown TTS engine: {name}")
