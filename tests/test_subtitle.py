from types import SimpleNamespace

from worker.subtitle import _build_srt, _srt_timestamp


def test_srt_timestamp_formatting():
    assert _srt_timestamp(0) == "00:00:00,000"
    assert _srt_timestamp(65.5) == "00:01:05,500"
    assert _srt_timestamp(3661.001) == "01:01:01,001"


def test_build_srt_uses_persian_text_and_clip_relative_time():
    segments = [
        SimpleNamespace(start=10.0, end=12.5, text_original="hello", text_fa="سلام"),
        SimpleNamespace(start=13.0, end=14.0, text_original="bye", text_fa=None),
    ]
    srt = _build_srt(segments, clip_start=10.0)

    assert "1\n00:00:00,000 --> 00:00:02,500\nسلام" in srt
    assert "2\n00:00:03,000 --> 00:00:04,000\nbye" in srt
