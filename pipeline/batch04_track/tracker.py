"""Batch 04 - Track.

ByteTrack dijalankan lewat Ultralytics (`model.track`). Kelas ini membungkusnya
dan mencatat riwayat track supaya kita bisa menghitung objek unik
(satu truk yang muncul di 100 frame dihitung 1, bukan 100).
"""
from __future__ import annotations

from collections import Counter

import numpy as np

from pipeline.types import Detection


class TrackHistory:
    def __init__(self) -> None:
        self._tracks: dict[int, dict] = {}

    def update(self, frame_id: int, detections: list[Detection]) -> None:
        for det in detections:
            if det.track_id is None:
                continue
            info = self._tracks.setdefault(
                det.track_id,
                {"class_name": det.class_name, "first_frame": frame_id, "last_frame": frame_id, "frames": 0},
            )
            info["last_frame"] = frame_id
            info["frames"] += 1

    def unique_counts(self) -> dict[str, int]:
        return dict(Counter(t["class_name"] for t in self._tracks.values()))

    def __len__(self) -> int:
        return len(self._tracks)


class Tracker:
    def __init__(self, detector, enabled: bool = False):
        self.detector = detector
        self.enabled = enabled
        self.history = TrackHistory()

    def process(self, image: np.ndarray, frame_id: int) -> list[Detection]:
        detections = self.detector.detect(image, track=self.enabled)
        if self.enabled:
            self.history.update(frame_id, detections)
        return detections