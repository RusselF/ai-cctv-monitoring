"""Batch 05 - Event.

Event per objek:
  Tanpa tracking : `object_in_zone` untuk setiap deteksi di dalam zona.
  Dengan tracking: `zone_enter` sekali saat objek masuk, `zone_exit` saat keluar.

Event per zona (hanya jika zona punya `congestion_threshold`):
  Tanpa tracking : `congestion` pada setiap frame yang jumlah objeknya >= threshold.
  Dengan tracking: `congestion_start` / `congestion_end` saat zona mulai/berhenti padat.

Deteksi dengan confidence < min_confidence diabaikan untuk event
(ambang event bisa lebih ketat dari ambang deteksi).
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from pipeline.batch03_zone import Zone
from pipeline.types import Detection, Event, Frame


class EventGenerator:
    def __init__(
        self,
        tracked: bool = False,
        min_confidence: float = 0.0,
        enter_frames: int = 1,
        exit_grace: int = 0,
    ):
        self.tracked = tracked
        self.min_confidence = min_confidence
        self.enter_frames = max(1, enter_frames)  # frame berturut-turut di dalam zona sebelum zone_enter
        self.exit_grace = max(0, exit_grace)      # frame boleh "hilang" sebelum zone_exit
        self._active: dict[tuple[int, str], Detection] = {}
        self._pending: dict[tuple[int, str], int] = {}
        self._missing: dict[tuple[int, str], int] = {}
        self._congested: dict[str, Zone] = {}

    def _threshold(self, zone: Zone) -> float:
        """Ambang confidence untuk zona ini: milik zona jika ada, kalau tidak ambang global."""
        return zone.min_confidence if zone.min_confidence is not None else self.min_confidence

    def _event(self, kind: str, det: Detection, zone: Zone, frame: Frame) -> Event:
        return Event(
            event_type=kind,
            class_name=det.class_name,
            zone=zone.name,
            confidence=round(det.confidence, 4),
            timestamp=frame.timestamp.isoformat(),
            source=frame.source_name,
            frame_id=frame.frame_id,
            track_id=det.track_id,
        )

    def _zone_event(self, kind: str, zone: Zone, count: int, conf: float, frame: Frame) -> Event:
        return Event(
            event_type=kind,
            class_name="vehicle",
            zone=zone.name,
            confidence=round(conf, 4),
            timestamp=frame.timestamp.isoformat(),
            source=frame.source_name,
            frame_id=frame.frame_id,
            count=count,
        )

    def process(self, frame: Frame, matches: list[tuple[Detection, Zone]]) -> list[Event]:
        matches = [(d, z) for d, z in matches if d.confidence >= self._threshold(z)]
        events = self._object_events(frame, matches)
        events += self._congestion_events(frame, matches)
        return events

    def _object_events(self, frame: Frame, matches: list[tuple[Detection, Zone]]) -> list[Event]:
        matches = [(d, z) for d, z in matches if z.object_events]
        if not self.tracked:
            return [self._event("object_in_zone", d, z, frame) for d, z in matches]

        events: list[Event] = []
        zones_by_name = {z.name: z for _, z in matches}
        current: dict[tuple[int, str], Detection] = {}
        for det, zone in matches:
            if det.track_id is None:
                events.append(self._event("object_in_zone", det, zone, frame))
            else:
                current[(det.track_id, zone.name)] = det

        # masuk: harus terlihat di dalam zona selama `enter_frames` frame berturut-turut
        for key, det in current.items():
            if key in self._active:
                self._active[key] = det
                self._missing.pop(key, None)
                continue
            seen = self._pending.get(key, 0) + 1
            if seen >= self.enter_frames:
                self._active[key] = det
                self._pending.pop(key, None)
                events.append(self._event("zone_enter", det, zones_by_name[key[1]], frame))
            else:
                self._pending[key] = seen
        for key in [k for k in self._pending if k not in current]:
            del self._pending[key]  # terputus sebelum cukup lama: dianggap bukan masuk

        # keluar: baru dicatat setelah hilang lebih dari `exit_grace` frame berturut-turut
        for key in [k for k in self._active if k not in current]:
            missed = self._missing.get(key, 0) + 1
            if missed > self.exit_grace:
                det = self._active.pop(key)
                self._missing.pop(key, None)
                exit_zone = zones_by_name.get(key[1]) or Zone(name=key[1], points=[])
                events.append(self._event("zone_exit", det, exit_zone, frame))
            else:
                self._missing[key] = missed
        return events

    def _congestion_events(self, frame: Frame, matches: list[tuple[Detection, Zone]]) -> list[Event]:
        per_zone: dict[str, list[Detection]] = defaultdict(list)
        zones: dict[str, Zone] = {}
        for det, zone in matches:
            per_zone[zone.name].append(det)
            zones[zone.name] = zone

        current: dict[str, tuple[Zone, int, float]] = {}
        for name, dets in per_zone.items():
            zone = zones[name]
            if zone.congestion_threshold and len(dets) >= zone.congestion_threshold:
                mean_conf = sum(d.confidence for d in dets) / len(dets)
                current[name] = (zone, len(dets), mean_conf)

        events: list[Event] = []
        if not self.tracked:
            return [self._zone_event("congestion", z, n, c, frame) for z, n, c in current.values()]

        for name, (zone, n, c) in current.items():
            if name not in self._congested:
                events.append(self._zone_event("congestion_start", zone, n, c, frame))
        for name in set(self._congested) - set(current):
            events.append(self._zone_event("congestion_end", self._congested[name], 0, 0.0, frame))
        self._congested = {name: zone for name, (zone, _, _) in current.items()}
        return events


class EventWriter:
    """Simpan event sebagai JSON Lines. Nanti bisa diganti/ditambah penulisan ke database."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, events: list[Event]) -> None:
        if not events:
            return
        with self.path.open("a", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")