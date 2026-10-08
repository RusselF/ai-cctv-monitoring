"""FastAPI: membaca event yang disimpan pipeline.

Jalankan:  uvicorn api.main:create_app --factory --reload
Dokumentasi interaktif: http://127.0.0.1:8000/docs
"""
from __future__ import annotations

from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from api import schemas
from storage import repository
from storage.session import make_engine, make_session_factory


def create_app(db_url: str | None = None) -> FastAPI:
    factory = make_session_factory(make_engine(db_url))

    app = FastAPI(title="AI CCTV Monitoring API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # dashboard Next.js
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    def get_session():
        with factory() as session:
            yield session

    def event_filter(
        camera: str | None = Query(None, description="Nama kamera"),
        zone: str | None = Query(None, description="Nama zona"),
        event_type: str | None = Query(None, description="zone_enter, zone_exit, object_in_zone, congestion, ..."),
        class_name: str | None = Query(None, description="car, motorcycle, bus, truck, ..."),
        run_id: str | None = Query(None, description="ID satu kali jalan pipeline"),
        since: datetime | None = Query(None, description="Waktu mulai (ISO 8601)"),
        until: datetime | None = Query(None, description="Waktu akhir (ISO 8601)"),
    ) -> repository.EventFilter:
        return repository.EventFilter(camera, zone, event_type, class_name, run_id, since, until)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/cameras", response_model=list[schemas.CameraOut])
    def cameras(session: Session = Depends(get_session)):
        return repository.list_cameras(session)

    @app.get("/cameras/{name}/zones", response_model=list[schemas.ZoneOut])
    def camera_zones(name: str, session: Session = Depends(get_session)):
        zones = repository.list_zones(session, name)
        if zones is None:
            raise HTTPException(status_code=404, detail=f"Kamera '{name}' tidak ditemukan")
        return zones

    @app.get("/runs", response_model=list[schemas.RunOut])
    def runs(session: Session = Depends(get_session)):
        return repository.list_runs(session)

    @app.get("/events", response_model=schemas.EventPage)
    def events(
        flt: repository.EventFilter = Depends(event_filter),
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
        session: Session = Depends(get_session),
    ):
        total, items = repository.list_events(session, flt, limit, offset)
        return {"total": total, "limit": limit, "offset": offset, "items": items}

    @app.get("/stats", response_model=schemas.StatsOut)
    def stats(flt: repository.EventFilter = Depends(event_filter), session: Session = Depends(get_session)):
        return repository.event_stats(session, flt)

    return app