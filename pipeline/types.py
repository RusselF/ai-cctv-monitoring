"""Struktur data bersama yang dipakai semua batch."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

import numpy as np


@dataclass
class Frame:
    frame_id: int
    image: np.ndarray
    source_name: str
    label: str = ""  # dipakai untuk nama file output
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Detection:
    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2 (piksel)
    track_id: int | None = None

    def anchor(self, mode: str = "bottom_center") -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        if mode == "center":
            return ((x1 + x2) / 2, (y1 + y2) / 2)
        return ((x1 + x2) / 2, y2)


@dataclass
class Event:
    event_type: str  # object_in_zone | zone_enter | zone_exit | congestion | congestion_start | congestion_end
    class_name: str
    zone: str
    confidence: float
    timestamp: str
    source: str
    frame_id: int
    track_id: int | None = None
    count: int | None = None  # dipakai event congestion

    def to_dict(self) -> dict:
        return asdict(self)