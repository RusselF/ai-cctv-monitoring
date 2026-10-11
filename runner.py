"""Entry point pipeline.

    python runner.py --config configs/config.yaml [--limit 20]
"""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

import cv2
import yaml

from pipeline.batch01_preprocess import preprocess
from pipeline.batch02_detect import Detector
from pipeline.batch03_zone import assign_zones, load_zones
from pipeline.batch04_track import Tracker
from pipeline.batch05_event import EventGenerator, EventWriter
from pipeline.batch06_visualize import draw
from pipeline.sources import build_source

log = logging.getLogger("runner")


def _open_video(path: Path, source, out_cfg: dict, size: tuple[int, int]) -> cv2.VideoWriter:
    """Buka penulis video hasil. fps = fps sumber / frame_stride (kecepatan tetap terlihat normal)."""
    src_fps = getattr(source, "fps", None)
    fps = out_cfg.get("video_fps") or (src_fps / getattr(source, "frame_stride", 1) if src_fps else 10.0)
    video = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    if not video.isOpened():
        raise IOError(f"Tidak bisa membuat video output: {path}")
    return video


def run(cfg: dict, limit: int | None = None) -> dict:
    out_dir = Path(cfg["output"]["dir"])
    annotated_dir = out_dir / "annotated"
    annotated_dir.mkdir(parents=True, exist_ok=True)

    source = build_source(cfg["source"])
    m = cfg["model"]
    detector = Detector(
        m["weights"], m.get("conf", 0.35), m.get("imgsz", 640), m.get("classes"),
        m.get("device"), cfg["tracking"].get("tracker", "bytetrack.yaml"),
    )
    tracked = bool(cfg["tracking"].get("enabled", False))
    tracker = Tracker(detector, enabled=tracked)
    zones = load_zones(cfg["zones"]["file"])
    anchor = cfg["zones"].get("anchor", "bottom_center")
    ev = cfg.get("events", {})
    generator = EventGenerator(
        tracked=tracked,
        min_confidence=ev.get("min_confidence", 0.0),
        enter_frames=ev.get("enter_frames", 1),
        exit_grace=ev.get("exit_grace", 0),
    )
    writers = [EventWriter(out_dir / "events" / "events.jsonl")]
    if cfg.get("database"):
        from pipeline.batch05_event.db_writer import DatabaseEventWriter  # butuh sqlalchemy

        db = cfg["database"]
        camera_name = cfg.get("camera", {}).get("name") or out_dir.name
        writers.append(
            DatabaseEventWriter(db.get("url"), camera_name, zones, source_type=cfg["source"]["type"])
        )
        log.info("event juga disimpan ke database (kamera=%s)", camera_name)

    out_cfg = cfg["output"]
    save_jpg = out_cfg.get("save_annotated", True)
    save_video = out_cfg.get("save_video", False)
    video = None

    n_frames = n_events = 0
    started = time.perf_counter()
    try:
        for frame in source:
            frame.image = preprocess(frame.image, cfg.get("preprocess", {}).get("max_side"))
            h, w = frame.image.shape[:2]

            detections = tracker.process(frame.image, frame.frame_id)
            matches = assign_zones(detections, zones, (w, h), anchor)
            events = generator.process(frame, matches)
            for sink in writers:
                sink.write(events)

            if save_jpg or save_video:
                annotated = draw(frame.image, detections, zones, matches)
                if save_jpg:
                    cv2.imwrite(str(annotated_dir / f"{frame.label}.jpg"), annotated)
                if save_video:
                    if video is None:
                        video = _open_video(out_dir / "annotated.mp4", source, out_cfg, (w, h))
                    video.write(annotated)

            n_frames += 1
            n_events += len(events)
            log.info("frame=%s detections=%d events=%d", frame.label, len(detections), len(events))
            if limit and n_frames >= limit:
                break
    finally:
        if video is not None:
            video.release()

    elapsed = time.perf_counter() - started
    summary = {
        "frames": n_frames,
        "events": n_events,
        "seconds": round(elapsed, 1),
        "fps": round(n_frames / elapsed, 2) if elapsed > 0 else 0.0,
    }
    if tracked:
        summary["unique_objects"] = tracker.history.unique_counts()
    log.info("selesai: %s", summary)
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="AI CCTV Monitoring pipeline")
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument("--limit", type=int, default=None, help="batasi jumlah frame (untuk tes cepat)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    run(cfg, args.limit)


if __name__ == "__main__":
    main()