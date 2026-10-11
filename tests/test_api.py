from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from pipeline.batch03_zone import Zone
from pipeline.batch05_event.db_writer import DatabaseEventWriter
from pipeline.types import Event

SQUARE = [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)]
ZONES = [Zone("road_zone", SQUARE, classes=frozenset({"car"}), min_confidence=0.4), Zone("queue_zone", SQUARE)]


def ev(kind, cls, frame, zone="road_zone", track=1, count=None, second=0):
    ts = datetime(2026, 10, 7, 10, 0, second, tzinfo=timezone.utc).isoformat()
    return Event(kind, cls, zone, 0.9, ts, "clip", frame, track, count, video_time=frame / 30)


@pytest.fixture()
def client(tmp_path):
    url = f"sqlite:///{tmp_path / 'm.db'}"
    writer = DatabaseEventWriter(url, "road-01", ZONES, source_type="video_file", run_id="run-a")
    writer.write([
        ev("zone_enter", "car", 1, track=1, second=1),
        ev("zone_enter", "motorcycle", 2, track=2, second=2),
        ev("zone_exit", "car", 3, track=1, second=3),
        ev("congestion", "vehicle", 4, zone="queue_zone", track=None, count=8, second=4),
    ])
    return TestClient(create_app(url))


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_cameras_and_zones(client):
    cams = client.get("/cameras").json()
    assert cams == [{"id": 1, "name": "road-01", "source_type": "video_file"}]
    zones = client.get("/cameras/road-01/zones").json()
    assert [z["name"] for z in zones] == ["queue_zone", "road_zone"]
    road = next(z for z in zones if z["name"] == "road_zone")
    assert road["classes"] == ["car"] and road["min_confidence"] == 0.4 and len(road["points"]) == 4


def test_unknown_camera_returns_404(client):
    r = client.get("/cameras/nope/zones")
    assert r.status_code == 404


def test_events_default_newest_first(client):
    body = client.get("/events").json()
    assert body["total"] == 4 and body["limit"] == 100 and body["offset"] == 0
    assert [e["frame_id"] for e in body["items"]] == [4, 3, 2, 1]
    first = body["items"][0]
    assert first["event_type"] == "congestion" and first["count"] == 8 and first["camera"] == "road-01"


def test_events_filters(client):
    assert client.get("/events", params={"event_type": "zone_enter"}).json()["total"] == 2
    assert client.get("/events", params={"class_name": "car"}).json()["total"] == 2
    assert client.get("/events", params={"zone": "queue_zone"}).json()["total"] == 1
    assert client.get("/events", params={"camera": "nope"}).json()["total"] == 0
    both = client.get("/events", params={"event_type": "zone_enter", "class_name": "car"}).json()
    assert both["total"] == 1 and both["items"][0]["track_id"] == 1


def test_events_pagination_and_validation(client):
    page = client.get("/events", params={"limit": 2, "offset": 1}).json()
    assert page["total"] == 4 and [e["frame_id"] for e in page["items"]] == [3, 2]
    assert client.get("/events", params={"limit": 0}).status_code == 422
    assert client.get("/events", params={"limit": 5000}).status_code == 422


def test_events_time_range(client):
    r = client.get("/events", params={"since": "2026-10-07T10:00:03+00:00"}).json()
    assert [e["frame_id"] for e in r["items"]] == [4, 3]
    r = client.get("/events", params={"until": "2026-10-07T17:00:02+07:00"}).json()   # = 10:00:02 UTC
    assert [e["frame_id"] for e in r["items"]] == [2, 1]


def test_stats(client):
    s = client.get("/stats").json()
    assert s["total"] == 4
    assert s["by_event_type"] == {"zone_enter": 2, "zone_exit": 1, "congestion": 1}
    assert s["by_zone"] == {"road_zone": 3, "queue_zone": 1}
    only_cars = client.get("/stats", params={"class_name": "car"}).json()
    assert only_cars["total"] == 2


def test_runs(client):
    runs = client.get("/runs").json()
    assert len(runs) == 1 and runs[0]["run_id"] == "run-a" and runs[0]["events"] == 4

def test_timestamps_carry_utc_offset(client):
    ts = client.get("/events").json()["items"][0]["timestamp"]
    assert ts.endswith("Z") or ts.endswith("+00:00")
    run = client.get("/runs").json()[0]
    assert run["first_event"].endswith(("Z", "+00:00")) and run["last_event"].endswith(("Z", "+00:00"))

def test_events_include_video_time(client):
    first = client.get("/events").json()["items"][0]            # frame 4
    assert first["video_time"] == pytest.approx(4 / 30)