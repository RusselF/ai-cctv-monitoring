"""Batch 03 - Zone. Cek apakah titik anchor sebuah deteksi berada di dalam polygon zona."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from shapely.geometry import Point, Polygon

from pipeline.types import Detection


@dataclass
class Zone:
    name: str
    points: list[tuple[float, float]]
    normalized: bool = True
    classes: frozenset = frozenset()
    congestion_threshold: int | None = None  # jumlah objek dalam zona yang dianggap padat
    min_confidence: float | None = None      # ambang event khusus zona ini (None = pakai ambang global)
    object_events: bool = True               # False = zona hanya untuk hitungan/congestion
    _cache: dict = field(default_factory=dict, repr=False, compare=False)

    def _pixel_points(self, size: tuple[int, int]) -> list[tuple[float, float]]:
        w, h = size
        if self.normalized:
            return [(x * w, y * h) for x, y in self.points]
        return list(self.points)

    def polygon(self, size: tuple[int, int]) -> Polygon:
        key = size if self.normalized else None
        if key not in self._cache:
            self._cache[key] = Polygon(self._pixel_points(size))
        return self._cache[key]

    def pixel_points(self, size: tuple[int, int]) -> list[tuple[int, int]]:
        return [(int(x), int(y)) for x, y in self._pixel_points(size)]

    def accepts(self, class_name: str) -> bool:
        return not self.classes or class_name in self.classes


def load_zones(path: str | Path) -> list[Zone]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    zones = []
    for item in data.get("zones", []):
        points = [tuple(p) for p in item["points"]]
        if len(points) < 3:
            raise ValueError(f"Zona '{item['name']}' butuh minimal 3 titik")
        zones.append(
            Zone(
                name=item["name"],
                points=points,
                normalized=item.get("coords", "normalized") == "normalized",
                classes=frozenset(item.get("classes", [])),
                congestion_threshold=item.get("congestion_threshold"),
                min_confidence=item.get("min_confidence"),
                object_events=item.get("object_events", True),
            )
        )
    return zones


def assign_zones(
    detections: list[Detection],
    zones: list[Zone],
    frame_size: tuple[int, int],
    anchor: str = "bottom_center",
) -> list[tuple[Detection, Zone]]:
    """Kembalikan pasangan (deteksi, zona) untuk setiap deteksi yang berada di dalam zona."""
    matches = []
    for det in detections:
        point = Point(det.anchor(anchor))
        for zone in zones:
            if zone.accepts(det.class_name) and zone.polygon(frame_size).covers(point):
                matches.append((det, zone))
    return matches