"""Batch 06 - Visualize. Gambar zona, bounding box, label, dan confidence."""
from __future__ import annotations

import cv2
import numpy as np

from pipeline.types import Detection

GREEN = (0, 200, 0)
RED = (0, 0, 255)
YELLOW = (0, 215, 255)


def draw(
    image: np.ndarray,
    detections: list[Detection],
    zones: list,
    matches: list | None = None,
) -> np.ndarray:
    h, w = image.shape[:2]
    overlay = image.copy()
    polys = [np.array(z.pixel_points((w, h)), np.int32) for z in zones]
    for poly in polys:
        if len(poly) >= 3:
            cv2.fillPoly(overlay, [poly], YELLOW)
    out = cv2.addWeighted(overlay, 0.2, image, 0.8, 0)

    for zone, poly in zip(zones, polys):
        if len(poly) >= 3:
            cv2.polylines(out, [poly], True, YELLOW, 2)
            cv2.putText(out, zone.name, tuple(poly[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.5, YELLOW, 2)

    in_zone = {id(d) for d, _ in (matches or [])}
    for det in detections:
        x1, y1, x2, y2 = map(int, det.bbox)
        color = RED if id(det) in in_zone else GREEN
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        label = f"{det.class_name} {det.confidence:.0%}"
        if det.track_id is not None:
            label += f" #{det.track_id}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        top = max(y1 - th - 6, 0)
        cv2.rectangle(out, (x1, top), (x1 + tw + 4, top + th + 6), color, -1)
        cv2.putText(out, label, (x1 + 2, top + th + 1), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    return out