from datetime import datetime, timezone

from pipeline.batch03_zone import Zone
from pipeline.batch05_event.db_writer import DatabaseEventWriter
from pipeline.types import Event
from storage import repository
from storage.session import make_engine, make_session_factory

SQUARE = [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)]
ZONES = [
    Zone("road_zone", SQUARE, classes=frozenset({"car", "motorcycle"}), min_confidence=0.4),
    Zone("queue_zone", SQUARE, congestion_threshold=6),
]


def make_event(kind="zone_enter", cls="car", zone="road_zone", conf=0.9, frame=1, track=7, count=None, ts=None):
    ts = ts or datetime(2026, 10, 7, 10, 0, 0, tzinfo=timezone.utc).isoformat()
    return Event(kind, cls, zone, conf, ts, "clip", frame, track, count)


def db_url(tmp_path):
    return f"sqlite:///{tmp_path / 'monitoring.db'}"


def test_writer_registers_camera_and_zones(tmp_path):
    DatabaseEventWriter(db_url(tmp_path), "road-01", ZONES, source_type="video_file")
    session = make_session_factory(make_engine(db_url(tmp_path)))()
    cameras = repository.list_cameras(session)
    assert [(c.name, c.source_type) for c in cameras] == [("road-01", "video_file")]
    zones = repository.list_zones(session, "road-01")
    assert [z.name for z in zones] == ["queue_zone", "road_zone"]
    road = next(z for z in zones if z.name == "road_zone")
    assert road.classes == ["car", "motorcycle"] and road.min_confidence == 0.4
    assert repository.list_zones(session, "tidak-ada") is None


def test_rerun_updates_zones_without_duplicates(tmp_path):
    DatabaseEventWriter(db_url(tmp_path), "road-01", ZONES)
    changed = [Zone("road_zone", SQUARE, min_confidence=0.3)]
    DatabaseEventWriter(db_url(tmp_path), "road-01", changed)
    session = make_session_factory(make_engine(db_url(tmp_path)))()
    zones = repository.list_zones(session, "road-01")
    assert len(zones) == 2
    assert next(z for z in zones if z.name == "road_zone").min_confidence == 0.3


def test_write_and_filter_events(tmp_path):
    w = DatabaseEventWriter(db_url(tmp_path), "road-01", ZONES, run_id="run-a")
    w.write([
        make_event("zone_enter", "car", frame=1),
        make_event("zone_enter", "motorcycle", frame=2, track=8),
        make_event("zone_exit", "car", frame=3),
        make_event("congestion", "vehicle", zone="queue_zone", conf=0.6, frame=4, track=None, count=8),
    ])
    session = make_session_factory(make_engine(db_url(tmp_path)))()

    total, items = repository.list_events(session, repository.EventFilter())
    assert total == 4 and len(items) == 4

    total, items = repository.list_events(session, repository.EventFilter(event_type="zone_enter"))
    assert total == 2 and {i["class_name"] for i in items} == {"car", "motorcycle"}

    total, items = repository.list_events(session, repository.EventFilter(zone="queue_zone"))
    assert total == 1 and items[0]["count"] == 8 and items[0]["camera"] == "road-01"

    total, items = repository.list_events(session, repository.EventFilter(run_id="nope"))
    assert total == 0 and items == []


def test_pagination_and_order(tmp_path):
    w = DatabaseEventWriter(db_url(tmp_path), "road-01", ZONES)
    w.write([
        make_event(frame=i, ts=datetime(2026, 10, 7, 10, 0, i, tzinfo=timezone.utc).isoformat())
        for i in range(5)
    ])
    session = make_session_factory(make_engine(db_url(tmp_path)))()
    total, page = repository.list_events(session, repository.EventFilter(), limit=2, offset=1)
    assert total == 5
    assert [i["frame_id"] for i in page] == [3, 2]       # terbaru dulu


def test_time_filter_uses_utc(tmp_path):
    w = DatabaseEventWriter(db_url(tmp_path), "road-01", ZONES)
    w.write([make_event(ts="2026-10-07T10:00:00+00:00")])
    session = make_session_factory(make_engine(db_url(tmp_path)))()
    # 17:30 WIB (UTC+7) = 10:30 UTC -> setelah event
    after = repository.EventFilter(since=datetime.fromisoformat("2026-10-07T17:30:00+07:00"))
    before = repository.EventFilter(until=datetime.fromisoformat("2026-10-07T17:30:00+07:00"))
    assert repository.list_events(session, after)[0] == 0
    assert repository.list_events(session, before)[0] == 1


def test_stats_and_runs(tmp_path):
    w = DatabaseEventWriter(db_url(tmp_path), "road-01", ZONES, run_id="run-a")
    w.write([make_event("zone_enter", "car"), make_event("zone_enter", "car", frame=2, track=9),
             make_event("zone_exit", "motorcycle", frame=3, track=8)])
    session = make_session_factory(make_engine(db_url(tmp_path)))()
    stats = repository.event_stats(session, repository.EventFilter())
    assert stats["total"] == 3
    assert stats["by_event_type"] == {"zone_enter": 2, "zone_exit": 1}
    assert stats["by_class"] == {"car": 2, "motorcycle": 1}
    assert stats["by_zone"] == {"road_zone": 3}
    runs = repository.list_runs(session)
    assert runs[0]["run_id"] == "run-a" and runs[0]["events"] == 3 and runs[0]["camera"] == "road-01"