"""Batch 01 - Preprocess.

YOLO sudah melakukan letterbox sendiri, jadi di sini kita hanya
memperkecil gambar yang terlalu besar agar inference & penyimpanan lebih ringan.
Semua koordinat (bbox, zona) berikutnya mengacu ke ukuran gambar hasil preprocess.
"""
from __future__ import annotations

import cv2
import numpy as np


def preprocess(image: np.ndarray, max_side: int | None = None) -> np.ndarray:
    if not max_side:
        return image
    h, w = image.shape[:2]
    scale = max_side / max(h, w)
    if scale >= 1:
        return image
    return cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)