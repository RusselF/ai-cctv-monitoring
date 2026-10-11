"""Abstraksi sumber input.

Pipeline hanya mengenal BaseSource. Ganti image folder -> video -> RTSP
cukup dengan mengganti `source.type` di config, tanpa mengubah batch lain.
"""
from __future__ import annotations

import logging
import os
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator

import cv2

from pipeline.types import Frame

log = logging.getLogger(__name__)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


class BaseSource(ABC):
    name: str

    @abstractmethod
    def __iter__(self) -> Iterator[Frame]: ...


class ImageFolderSource(BaseSource):
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.is_dir():
            raise FileNotFoundError(f"Folder gambar tidak ditemukan: {self.path}")
        self.name = self.path.name

    def __iter__(self) -> Iterator[Frame]:
        files = sorted(p for p in self.path.iterdir() if p.suffix.lower() in IMAGE_EXTS)
        for idx, file in enumerate(files):
            image = cv2.imread(str(file))
            if image is None:
                continue
            yield Frame(frame_id=idx, image=image, source_name=self.name, label=file.stem)


class VideoFileSource(BaseSource):
    timed = True  # frame membawa waktu di dalam video

    def __init__(self, path: str | Path, frame_stride: int = 1):
        self.path = str(path)
        self.frame_stride = max(1, int(frame_stride))
        self.name = Path(self.path).stem
        self.fps = 30.0  # diperbarui dari file video saat dibaca

    def __iter__(self) -> Iterator[Frame]:
        cap = cv2.VideoCapture(self.path)
        if not cap.isOpened():
            raise IOError(f"Tidak bisa membuka sumber video: {self.path}")
        self.fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        try:
            idx = 0
            while True:
                ok, image = cap.read()
                if not ok:
                    break
                if idx % self.frame_stride == 0:
                    video_time = round(idx / self.fps, 3) if self.timed else None
                    yield Frame(idx, image, self.name, label=f"{self.name}_{idx:06d}", video_time=video_time)
                idx += 1
        finally:
            cap.release()


class _LatestFrame:
    """Menyimpan hanya frame terbaru dari thread pembaca; frame lama yang belum diambil dibuang."""

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._frame_id = -1
        self._image = None
        self.finished = False

    def put(self, frame_id: int, image) -> None:
        with self._cond:
            self._frame_id, self._image = frame_id, image
            self._cond.notify_all()

    def finish(self) -> None:
        with self._cond:
            self.finished = True
            self._cond.notify_all()

    def wait_newer(self, last_id: int, timeout: float):
        with self._cond:
            self._cond.wait_for(lambda: self._frame_id > last_id or self.finished, timeout)
            if self._frame_id > last_id:
                return self._frame_id, self._image
            return None, None


class RTSPSource(BaseSource):
    """Stream RTSP.

    Thread pembaca terus menarik frame dan hanya menyimpan yang terbaru, jadi pipeline yang
    lebih lambat dari stream selalu memproses gambar terkini (frame di antaranya dilewati)
    dan tidak tertinggal makin jauh. Jika stream putus, koneksi dicoba ulang; setelah
    `max_retries` kegagalan berturut-turut, iterasi berhenti.
    """

    timed = False  # fps stream tidak bisa diandalkan, jadi tidak ada waktu video

    def __init__(self, url: str, frame_stride: int = 1, reconnect_delay: float = 2.0, max_retries: int = 5):
        self.url = url
        self.name = "rtsp_stream"
        self.frame_stride = frame_stride  # tidak dipakai: frame dilewati otomatis sesuai kecepatan proses
        self.reconnect_delay = reconnect_delay
        self.max_retries = max_retries

    def _reader(self, state: _LatestFrame, stop: threading.Event) -> None:
        failures = 0
        frame_id = 0
        while not stop.is_set():
            cap = cv2.VideoCapture(self.url)
            try:
                if cap.isOpened():
                    while not stop.is_set():
                        ok, image = cap.read()
                        if not ok:
                            break
                        failures = 0
                        state.put(frame_id, image)
                        frame_id += 1
            finally:
                cap.release()
            if stop.is_set():
                break
            failures += 1
            if failures > self.max_retries:
                log.warning("RTSP: gagal tersambung %d kali berturut-turut, berhenti", failures - 1)
                break
            log.warning("RTSP terputus, mencoba lagi (%d/%d)", failures, self.max_retries)
            stop.wait(self.reconnect_delay)
        state.finish()

    def __iter__(self) -> Iterator[Frame]:
        # TCP lebih andal daripada UDP (tidak kehilangan paket); harus diatur sebelum capture dibuka
        os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
        state = _LatestFrame()
        stop = threading.Event()
        thread = threading.Thread(target=self._reader, args=(state, stop), daemon=True)
        thread.start()
        last_id = -1
        try:
            while True:
                frame_id, image = state.wait_newer(last_id, timeout=1.0)
                if image is None:
                    if state.finished:
                        break
                    continue
                last_id = frame_id
                yield Frame(frame_id, image, self.name, label=f"{self.name}_{frame_id:06d}")
        finally:
            stop.set()
            thread.join(timeout=3)


def build_source(cfg: dict) -> BaseSource:
    kind = cfg["type"]
    if kind == "image_folder":
        return ImageFolderSource(cfg["path"])
    if kind == "video_file":
        return VideoFileSource(cfg["path"], cfg.get("frame_stride", 1))
    if kind == "rtsp":
        return RTSPSource(
            cfg["path"],
            cfg.get("frame_stride", 1),
            cfg.get("reconnect_delay", 2.0),
            cfg.get("max_retries", 5),
        )
    raise ValueError(f"source.type tidak dikenal: {kind}")