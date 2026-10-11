"""Tabel database: cameras -> zones -> events."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    source_type: Mapped[str | None] = mapped_column(String(30), nullable=True)

    zones: Mapped[list["Zone"]] = relationship(back_populates="camera", cascade="all, delete-orphan")


class Zone(Base):
    __tablename__ = "zones"
    __table_args__ = (UniqueConstraint("camera_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id"))
    name: Mapped[str] = mapped_column(String(100))
    points: Mapped[list] = mapped_column(JSON)
    normalized: Mapped[bool] = mapped_column(default=True)
    classes: Mapped[list] = mapped_column(JSON, default=list)
    congestion_threshold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    camera: Mapped[Camera] = relationship(back_populates="zones")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id"), index=True)
    zone_id: Mapped[int | None] = mapped_column(ForeignKey("zones.id"), nullable=True, index=True)
    run_id: Mapped[str] = mapped_column(String(40), index=True)
    event_type: Mapped[str] = mapped_column(String(30), index=True)
    class_name: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)  # UTC, tanpa tzinfo
    frame_id: Mapped[int] = mapped_column(Integer)
    track_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    video_time: Mapped[float | None] = mapped_column(Float, nullable=True)  # detik di dalam video