"""Bentuk data yang dikirim API (response)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CameraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    source_type: str | None = None


class ZoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    points: list[list[float]]
    normalized: bool
    classes: list[str]
    congestion_threshold: int | None = None
    min_confidence: float | None = None


class EventOut(BaseModel):
    id: int
    camera: str
    zone: str | None
    run_id: str
    event_type: str
    class_name: str
    confidence: float
    timestamp: datetime
    frame_id: int
    track_id: int | None
    count: int | None


class EventPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[EventOut]


class RunOut(BaseModel):
    run_id: str
    camera: str
    events: int
    first_event: datetime
    last_event: datetime


class StatsOut(BaseModel):
    total: int
    by_event_type: dict[str, int]
    by_class: dict[str, int]
    by_zone: dict[str, int]