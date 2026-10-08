"""Penulis event ke database (selain JSONL). Aktif jika config punya bagian `database`."""
from __future__ import annotations

from datetime import datetime, timezone

from pipeline.batch03_zone import Zone
from pipeline.types import Event
from storage import repository
from storage.session import make_engine, make_session_factory


class DatabaseEventWriter:
    def __init__(
        self,
        url: str | None,
        camera_name: str,
        zones: list[Zone],
        source_type: str | None = None,
        run_id: str | None = None,
    ):
        self.run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        self._factory = make_session_factory(make_engine(url))
        with self._factory() as session:
            camera = repository.register_camera(session, camera_name, source_type)
            self.camera_id = camera.id
            self._zone_ids = repository.sync_zones(session, camera, zones)
            session.commit()

    def write(self, events: list[Event]) -> None:
        if not events:
            return
        with self._factory() as session:
            repository.insert_events(session, self.camera_id, self.run_id, self._zone_ids, events)
            session.commit()