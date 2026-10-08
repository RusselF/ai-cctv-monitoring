"""Batch 02 - Detect. Wrapper YOLO11 (Ultralytics)."""
from __future__ import annotations

import numpy as np

from pipeline.types import Detection


class Detector:
    def __init__(
        self,
        weights: str,
        conf: float = 0.35,
        imgsz: int = 640,
        classes: list[str] | None = None,
        device: str | None = None,
        tracker: str = "bytetrack.yaml",
    ):
        from ultralytics import YOLO  # import di sini agar modul lain bisa dites tanpa ultralytics

        self.model = YOLO(weights)
        self.conf = conf
        self.imgsz = imgsz
        self.device = device
        self.tracker = tracker
        self.names = self.model.names
        self.class_filter = set(classes) if classes else None

    def detect(self, image: np.ndarray, track: bool = False) -> list[Detection]:
        kwargs = dict(conf=self.conf, imgsz=self.imgsz, device=self.device, verbose=False)
        if track:
            results = self.model.track(image, persist=True, tracker=self.tracker, **kwargs)
        else:
            results = self.model.predict(image, **kwargs)
        return self._parse(results[0])

    def _parse(self, result) -> list[Detection]:
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return []
        ids = boxes.id.int().cpu().tolist() if boxes.id is not None else [None] * len(boxes)
        detections = []
        for xyxy, conf, cls, tid in zip(
            boxes.xyxy.cpu().tolist(),
            boxes.conf.cpu().tolist(),
            boxes.cls.int().cpu().tolist(),
            ids,
        ):
            name = self.names[cls]
            if self.class_filter and name not in self.class_filter:
                continue
            detections.append(Detection(name, float(conf), tuple(xyxy), tid))
        return detections