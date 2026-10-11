import numpy as np

from pipeline import sources
from pipeline.sources import RTSPSource, build_source


class FakeCapture:
    """Satu 'koneksi': bisa gagal dibuka atau menghasilkan N frame lalu putus."""

    def __init__(self, opens: bool, frames: int):
        self._opens, self._left = opens, frames

    def isOpened(self):
        return self._opens

    def read(self):
        if self._left <= 0:
            return False, None
        self._left -= 1
        return True, np.zeros((8, 8, 3), np.uint8)

    def release(self):
        pass


def patch_captures(monkeypatch, plan):
    """plan: daftar (opens, frames) untuk setiap percobaan sambung; setelah habis selalu gagal."""
    calls = iter(plan)
    attempts = []

    def factory(url):
        attempts.append(url)
        return FakeCapture(*next(calls, (False, 0)))

    monkeypatch.setattr(sources.cv2, "VideoCapture", factory)
    return attempts


def test_reconnects_after_drop_and_gives_up(monkeypatch):
    # sambung -> 3 frame -> putus -> gagal buka -> sambung lagi -> 2 frame -> putus -> semua gagal
    attempts = patch_captures(monkeypatch, [(True, 3), (False, 0), (True, 2)])
    src = RTSPSource("rtsp://cam/stream", reconnect_delay=0, max_retries=3)
    ids = [f.frame_id for f in src]
    assert ids == sorted(set(ids)) and len(ids) >= 1          # id naik terus (frame boleh terlewat)
    assert ids[-1] == 4                                       # 3 + 2 frame diterima total (id 0..4)
    assert len(attempts) >= 4                                 # ada percobaan sambung ulang


def test_stops_when_stream_never_opens(monkeypatch):
    attempts = patch_captures(monkeypatch, [])
    frames = list(RTSPSource("rtsp://nope", reconnect_delay=0, max_retries=2))
    assert frames == []
    assert len(attempts) == 3                                 # 1 percobaan awal + 2 ulangan


def test_frames_have_no_video_time(monkeypatch):
    patch_captures(monkeypatch, [(True, 2)])
    frames = list(RTSPSource("rtsp://cam", reconnect_delay=0, max_retries=0))
    assert frames and all(f.video_time is None for f in frames)


def test_build_source_passes_rtsp_options():
    src = build_source({"type": "rtsp", "path": "rtsp://cam/x", "reconnect_delay": 0.5, "max_retries": 9})
    assert isinstance(src, RTSPSource)
    assert (src.url, src.reconnect_delay, src.max_retries) == ("rtsp://cam/x", 0.5, 9)