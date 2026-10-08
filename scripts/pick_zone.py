"""Klik titik polygon pada gambar untuk mendapatkan koordinat zona (normalized 0..1).

    python scripts/pick_zone.py data/samples/nama_gambar.jpg

Klik kiri : tambah titik     Enter : cetak koordinat
r         : reset titik      q     : keluar
"""
import sys

import cv2
import numpy as np


def main(path: str) -> None:
    img = cv2.imread(path)
    if img is None:
        raise SystemExit(f"Tidak bisa membuka gambar: {path}")
    h, w = img.shape[:2]
    points: list[tuple[int, int]] = []

    def on_click(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            points.append((x, y))

    cv2.namedWindow("pick_zone")
    cv2.setMouseCallback("pick_zone", on_click)
    while True:
        view = img.copy()
        for p in points:
            cv2.circle(view, p, 4, (0, 215, 255), -1)
        if len(points) > 1:
            cv2.polylines(view, [np.array(points, np.int32)], len(points) > 2, (0, 215, 255), 2)
        cv2.imshow("pick_zone", view)
        key = cv2.waitKey(20) & 0xFF
        if key == 13 and len(points) >= 3:  # Enter
            print("points:", [[round(x / w, 3), round(y / h, 3)] for x, y in points])
        elif key == ord("r"):
            points.clear()
        elif key == ord("q"):
            break
    cv2.destroyAllWindows()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])