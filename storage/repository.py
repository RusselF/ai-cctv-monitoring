"""Operasi baca/tulis database. Dipakai oleh pipeline (menulis) dan API (membaca)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pipeline.batch03_zone import Zone as PipelineZone
from pipeline.types import Event as PipelineEvent
from storage.models import Camera, Event, Zone


def to_naive_utc(value: str | datetime) -> datetime:
    """Samakan semua waktu ke UTC tanpa tzinfo (SQLite tidak menyimpan zona waktu)."""
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value

def as_utc(value: datetime) -> datetime:
    """Waktu dari database (UTC tanpa tzinfo) -> UTC dengan tzinfo, agar JSON berakhiran +00:00."""
    return value.replace(tzinfo=timezone.utc)


# ---------- menulis ----------

def register_camera(session: Session, name: str, source_type: str | None = None) -> Camera:
    camera = session.scalar(select(Camera).where(Camera.name == name))
    if camera is None:
        camera = Camera(name=name, source_type=source_type)
        session.add(camera)
        session.flush()
    elif source_type:
        camera.source_type = source_type
    return camera


def sync_zones(session: Session, camera: Camera, zones: list[PipelineZone]) -> dict[str, int]:
    """Buat/perbarui zona milik kamera sesuai config. Mengembalikan {nama_zona: id}."""
    existing = {z.name: z for z in session.scalars(select(Zone).where(Zone.camera_id == camera.id))}
    rows = []
    for zone in zones:
        row = existing.get(zone.name) or Zone(camera_id=camera.id, name=zone.name)
        row.points = [list(p) for p in zone.points]
        row.normalized = zone.normalized
        row.classes = sorted(zone.classes)
        row.congestion_threshold = zone.congestion_threshold
        row.min_confidence = zone.min_confidence
        session.add(row)
        rows.append(row)
    session.flush()
    return {row.name: row.id for row in rows}


def insert_events(
    session: Session,
    camera_id: int,
    run_id: str,
    zone_ids: dict[str, int],
    events: list[PipelineEvent],
) -> None:
    session.add_all(
        Event(
            camera_id=camera_id,
            zone_id=zone_ids.get(e.zone),
            run_id=run_id,
            event_type=e.event_type,
            class_name=e.class_name,
            confidence=e.confidence,
            timestamp=to_naive_utc(e.timestamp),
            frame_id=e.frame_id,
            track_id=e.track_id,
            count=e.count,
        )
        for e in events
    )


# ---------- membaca ----------

@dataclass
class EventFilter:
    camera: str | None = None
    zone: str | None = None
    event_type: str | None = None
    class_name: str | None = None
    run_id: str | None = None
    since: datetime | None = None
    until: datetime | None = None

    def conditions(self) -> list:
        conds = []
        if self.camera:
            conds.append(Camera.name == self.camera)
        if self.zone:
            conds.append(Zone.name == self.zone)
        if self.event_type:
            conds.append(Event.event_type == self.event_type)
        if self.class_name:
            conds.append(Event.class_name == self.class_name)
        if self.run_id:
            conds.append(Event.run_id == self.run_id)
        if self.since:
            conds.append(Event.timestamp >= to_naive_utc(self.since))
        if self.until:
            conds.append(Event.timestamp <= to_naive_utc(self.until))
        return conds


def _joined(stmt):
    return stmt.join(Camera, Camera.id == Event.camera_id).outerjoin(Zone, Zone.id == Event.zone_id)


def list_events(session: Session, flt: EventFilter, limit: int = 100, offset: int = 0) -> tuple[int, list[dict]]:
    conds = flt.conditions()
    total = session.scalar(_joined(select(func.count(Event.id))).where(*conds)) or 0
    stmt = _joined(
        select(Event, Camera.name.label("camera"), Zone.name.label("zone"))
    ).where(*conds).order_by(Event.timestamp.desc(), Event.id.desc()).limit(limit).offset(offset)
    items = [
        {
            "id": e.id, "camera": camera, "zone": zone, "run_id": e.run_id,
            "event_type": e.event_type, "class_name": e.class_name, "confidence": e.confidence,
            "timestamp": as_utc(e.timestamp), "frame_id": e.frame_id, "track_id": e.track_id, "count": e.count,
        }
        for e, camera, zone in session.execute(stmt)
    ]
    return total, items


def event_stats(session: Session, flt: EventFilter) -> dict:
    conds = flt.conditions()

    def grouped(column) -> dict[str, int]:
        stmt = _joined(select(column, func.count(Event.id))).where(*conds).group_by(column)
        return {(key or "-"): n for key, n in session.execute(stmt)}

    return {
        "total": session.scalar(_joined(select(func.count(Event.id))).where(*conds)) or 0,
        "by_event_type": grouped(Event.event_type),
        "by_class": grouped(Event.class_name),
        "by_zone": grouped(Zone.name),
    }


def list_cameras(session: Session) -> list[Camera]:
    return list(session.scalars(select(Camera).order_by(Camera.name)))


def list_zones(session: Session, camera_name: str) -> list[Zone] | None:
    camera = session.scalar(select(Camera).where(Camera.name == camera_name))
    if camera is None:
        return None
    return list(session.scalars(select(Zone).where(Zone.camera_id == camera.id).order_by(Zone.name)))


def list_runs(session: Session) -> list[dict]:
    stmt = (
        select(
            Event.run_id, Camera.name, func.count(Event.id),
            func.min(Event.timestamp), func.max(Event.timestamp),
        )
        .join(Camera, Camera.id == Event.camera_id)
        .group_by(Event.run_id, Camera.name)
        .order_by(func.max(Event.timestamp).desc())
    )
    return [
        {"run_id": run_id, "camera": camera, "events": n, "first_event": as_utc(first), "last_event": as_utc(last)}
        for run_id, camera, n, first, last in session.execute(stmt)
    ]