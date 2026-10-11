import cv2
import numpy as np

from pipeline.sources import ImageFolderSource, RTSPSource, VideoFileSource


def test_video_frames_carry_video_time(tmp_path):
    clip = tmp_path / "clip.mp4"
    vw = cv2.VideoWriter(str(clip), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
    for _ in range(10):
        vw.write(np.zeros((48, 64, 3), np.uint8))
    vw.release()

    frames = list(VideoFileSource(clip, frame_stride=2))
    assert [f.frame_id for f in frames] == [0, 2, 4, 6, 8]
    assert [f.video_time for f in frames] == [0.0, 0.2, 0.4, 0.6, 0.8]
    assert RTSPSource("rtsp://x").timed is False


def test_image_frames_have_no_video_time(tmp_path):
    cv2.imwrite(str(tmp_path / "a.jpg"), np.zeros((20, 30, 3), np.uint8))
    assert list(ImageFolderSource(tmp_path))[0].video_time is None