"""Abstraksi sumber input.

Pipeline hanya mengenal BaseSource. Ganti image folder -> video -> RTSP
cukup dengan mengganti `source.type` di config, tanpa mengubah batch lain.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator

import cv2

from pipeline.types import Frame

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
        self.name = Path(self.path).stem

    def __iter__(self) -> Iterator[Frame]:
        files = sorted(p for p in self.path.iterdir() if p.suffix.lower() in IMAGE_EXTS)
        for idx, file in enumerate(files):
            image = cv2.imread(str(file))
            if image is None:
                continue
            yield Frame(frame_id=idx, image=image, source_name=self.name, label=file.stem)


class VideoFileSource(BaseSource):
    def __init__(self, path: str | Path, frame_stride: int = 1):
        self.path = str(path)
        self.frame_stride = max(1, int(frame_stride))
        self.name = Path(self.path).stem
        self.fps = 30.0

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
                    yield Frame(idx, image, self.name, label=f"{self.name}_{idx:06d}")
                idx += 1
        finally:
            cap.release()


class RTSPSource(VideoFileSource):
    """Stream RTSP. Memakai OpenCV VideoCapture yang sama dengan video file."""

    def __init__(self, url: str, frame_stride: int = 1):
        super().__init__(url, frame_stride)
        self.name = "rtsp_stream"


def build_source(cfg: dict) -> BaseSource:
    kind = cfg["type"]
    if kind == "image_folder":
        return ImageFolderSource(cfg["path"])
    if kind == "video_file":
        return VideoFileSource(cfg["path"], cfg.get("frame_stride", 1))
    if kind == "rtsp":
        return RTSPSource(cfg["path"], cfg.get("frame_stride", 1))
    raise ValueError(f"source.type tidak dikenal: {kind}")