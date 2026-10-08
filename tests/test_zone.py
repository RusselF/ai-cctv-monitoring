from pipeline.batch03_zone import Zone, assign_zones
from pipeline.types import Detection

SIZE = (1000, 500)  # w, h
SQUARE = [(0.2, 0.2), (0.8, 0.2), (0.8, 0.9), (0.2, 0.9)]


def det(cls, bbox, tid=None):
    return Detection(cls, 0.9, bbox, tid)


def test_inside_zone_creates_match():
    zone = Zone("loading", SQUARE)
    d = det("truck", (400, 100, 600, 400))  # bottom_center = (500, 400) -> di dalam
    assert assign_zones([d], [zone], SIZE) == [(d, zone)]


def test_outside_zone_no_match():
    zone = Zone("loading", SQUARE)
    d = det("truck", (10, 10, 100, 80))
    assert assign_zones([d], [zone], SIZE) == []


def test_anchor_bottom_center_vs_center():
    zone = Zone("z", [(0.0, 0.8), (1.0, 0.8), (1.0, 1.0), (0.0, 1.0)])  # strip bawah
    d = det("car", (400, 300, 600, 450))  # tengah di y=375 (luar), kaki di y=450 (dalam)
    assert len(assign_zones([d], [zone], SIZE, "bottom_center")) == 1
    assert len(assign_zones([d], [zone], SIZE, "center")) == 0


def test_class_filter():
    zone = Zone("restricted", SQUARE, classes=frozenset({"person"}))
    truck = det("truck", (400, 100, 600, 400))
    person = det("person", (400, 100, 600, 400))
    result = assign_zones([truck, person], [zone], SIZE)
    assert [d.class_name for d, _ in result] == ["person"]


def test_pixel_coordinates():
    zone = Zone("px", [(0, 0), (200, 0), (200, 200), (0, 200)], normalized=False)
    inside = det("car", (50, 50, 100, 100))
    outside = det("car", (300, 300, 400, 400))
    assert len(assign_zones([inside, outside], [zone], SIZE)) == 1


def test_normalized_zone_scales_with_frame_size():
    zone = Zone("z", SQUARE)
    d_small = det("car", (40, 20, 60, 40))     # frame 100x50 -> kaki (50, 40)
    assert len(assign_zones([d_small], [zone], (100, 50))) == 1
    assert len(assign_zones([d_small], [zone], (1000, 500))) == 0