import json

import numpy as np

from pipeline.batch03_zone import Zone
from pipeline.batch05_event import EventGenerator, EventWriter
from pipeline.types import Detection, Frame

ZONE = Zone("loading", [(0, 0), (1, 0), (1, 1), (0, 1)])
IMG = np.zeros((10, 10, 3), dtype=np.uint8)


def frame(i):
    return Frame(i, IMG, "cam", label=f"f{i}")


def test_untracked_one_event_per_detection():
    gen = EventGenerator(tracked=False)
    d1, d2 = Detection("truck", 0.9, (0, 0, 1, 1)), Detection("car", 0.8, (0, 0, 1, 1))
    events = gen.process(frame(0), [(d1, ZONE), (d2, ZONE)])
    assert [e.event_type for e in events] == ["object_in_zone"] * 2


def test_tracked_enter_once_then_exit():
    gen = EventGenerator(tracked=True)
    d = Detection("truck", 0.9, (0, 0, 1, 1), track_id=17)

    e1 = gen.process(frame(0), [(d, ZONE)])
    e2 = gen.process(frame(1), [(d, ZONE)])
    e3 = gen.process(frame(2), [(d, ZONE)])
    e4 = gen.process(frame(3), [])

    assert [e.event_type for e in e1] == ["zone_enter"]
    assert e2 == [] and e3 == []          # tidak ada event duplikat
    assert [e.event_type for e in e4] == ["zone_exit"]
    assert e4[0].track_id == 17 and e4[0].zone == "loading"


def test_tracked_reentry_creates_new_enter():
    gen = EventGenerator(tracked=True)
    d = Detection("car", 0.9, (0, 0, 1, 1), track_id=1)
    gen.process(frame(0), [(d, ZONE)])
    gen.process(frame(1), [])
    again = gen.process(frame(2), [(d, ZONE)])
    assert [e.event_type for e in again] == ["zone_enter"]


def test_writer_jsonl(tmp_path):
    gen = EventGenerator()
    d = Detection("truck", 0.94, (0, 0, 1, 1))
    events = gen.process(frame(0), [(d, ZONE)])
    path = tmp_path / "events" / "events.jsonl"
    EventWriter(path).write(events)
    row = json.loads(path.read_text().splitlines()[0])
    assert row["class_name"] == "truck" and row["zone"] == "loading"


# ---- min_confidence & congestion ----

def test_min_confidence_filters_weak_detections():
    gen = EventGenerator(min_confidence=0.5)
    weak = Detection("car", 0.36, (0, 0, 1, 1))
    strong = Detection("car", 0.89, (0, 0, 1, 1))
    events = gen.process(frame(0), [(weak, ZONE), (strong, ZONE)])
    assert [e.confidence for e in events] == [0.89]


BUSY = Zone("intersection", [(0, 0), (1, 0), (1, 1), (0, 1)], congestion_threshold=3)


def cars(n):
    return [(Detection("car", 0.8, (0, 0, 1, 1)), BUSY) for _ in range(n)]


def test_congestion_untracked_per_frame():
    gen = EventGenerator(tracked=False)
    below = [e for e in gen.process(frame(0), cars(2)) if e.event_type == "congestion"]
    above = [e for e in gen.process(frame(1), cars(4)) if e.event_type == "congestion"]
    assert below == []
    assert len(above) == 1 and above[0].count == 4 and above[0].zone == "intersection"


def test_congestion_tracked_start_and_end_once():
    gen = EventGenerator(tracked=True)

    def kinds(f, m):
        return [e.event_type for e in gen.process(frame(f), m) if e.event_type.startswith("congestion")]

    assert kinds(0, cars(2)) == []
    assert kinds(1, cars(3)) == ["congestion_start"]
    assert kinds(2, cars(5)) == []                      # masih padat, tidak ada event baru
    assert kinds(3, cars(1)) == ["congestion_end"]


def test_zone_without_threshold_never_congested():
    plain = Zone("plain", [(0, 0), (1, 0), (1, 1), (0, 1)])
    gen = EventGenerator()
    events = gen.process(frame(0), [(Detection("car", 0.9, (0, 0, 1, 1)), plain)] * 20)
    assert all(e.event_type != "congestion" for e in events)

def test_zone_min_confidence_overrides_global():
    strict = Zone("strict", [(0, 0), (1, 0), (1, 1), (0, 1)])                      # pakai global 0.5
    lenient = Zone("queue", [(0, 0), (1, 0), (1, 1), (0, 1)], min_confidence=0.25)
    gen = EventGenerator(min_confidence=0.5)
    weak = Detection("car", 0.3, (0, 0, 1, 1))
    events = gen.process(frame(0), [(weak, strict), (weak, lenient)])
    assert [e.zone for e in events] == ["queue"]

def test_zone_can_disable_object_events_but_keep_congestion():
    queue = Zone("queue", [(0, 0), (1, 0), (1, 1), (0, 1)], congestion_threshold=2, object_events=False)
    gen = EventGenerator()
    dets = [(Detection("car", 0.8, (0, 0, 1, 1)), queue) for _ in range(3)]
    kinds = [e.event_type for e in gen.process(frame(0), dets)]
    assert kinds == ["congestion"]

# ---- debounce (enter_frames & exit_grace) ----

def _tracked(d, in_zone):
    return [(d, ZONE)] if in_zone else []


def test_exit_grace_ignores_short_dropout():
    gen = EventGenerator(tracked=True, exit_grace=2)
    d = Detection("car", 0.9, (0, 0, 1, 1), track_id=5)
    pattern = [True, False, True, False, False, True]   # hilang sebentar, kembali dalam 2 frame
    kinds = [e.event_type for i, p in enumerate(pattern) for e in gen.process(frame(i), _tracked(d, p))]
    assert kinds == ["zone_enter"]                      # tidak ada exit/enter palsu


def test_exit_after_grace_exceeded():
    gen = EventGenerator(tracked=True, exit_grace=2)
    d = Detection("car", 0.9, (0, 0, 1, 1), track_id=5)
    pattern = [True, False, False, False, True]
    kinds = [e.event_type for i, p in enumerate(pattern) for e in gen.process(frame(i), _tracked(d, p))]
    assert kinds == ["zone_enter", "zone_exit", "zone_enter"]


def test_enter_frames_requires_consecutive_presence():
    gen = EventGenerator(tracked=True, enter_frames=3)
    d = Detection("car", 0.9, (0, 0, 1, 1), track_id=9)
    flicker = [True, False, True, False, True]          # tidak pernah 3 berturut-turut
    assert [e for i, p in enumerate(flicker) for e in gen.process(frame(i), _tracked(d, p))] == []
    gen2 = EventGenerator(tracked=True, enter_frames=3)
    steady = [True, True, True, True]
    kinds = [e.event_type for i, p in enumerate(steady) for e in gen2.process(frame(i), _tracked(d, p))]
    assert kinds == ["zone_enter"]