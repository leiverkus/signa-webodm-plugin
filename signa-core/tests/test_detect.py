# SPDX-License-Identifier: MIT
"""Synthetic round-trip: render an ArUco marker, then detect it back."""
import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")
aruco = pytest.importorskip("cv2.aruco")

from signa_core import detect_markers, make_dictionary  # noqa: E402


def _render_marker(dict_id, marker_id, side=240, pad=80):
    d = make_dictionary(dict_id, aruco)
    if hasattr(aruco, "generateImageMarker"):
        marker = aruco.generateImageMarker(d, marker_id, side)
    else:  # older OpenCV
        marker = aruco.drawMarker(d, marker_id, side)
    canvas = np.full((side + 2 * pad, side + 2 * pad), 255, dtype=np.uint8)
    canvas[pad:pad + side, pad:pad + side] = marker
    return cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)


def test_detect_synthetic_marker(tmp_path):
    img_path = tmp_path / "marker.png"
    cv2.imwrite(str(img_path), _render_marker(dict_id=1, marker_id=7))

    result = detect_markers([str(img_path)], dict_id=1, minrate=0.01, ignore=0.33)
    dets = result["marker.png"]

    assert dets, "no markers detected"
    ids = {d["id"] for d in dets}
    assert 7 in ids
    det = next(d for d in dets if d["id"] == 7)
    assert len(det["corners"]) == 4
    cx, cy = det["center"]
    # marker is centered on the canvas (side 240, pad 80 -> center at 200,200)
    assert abs(cx - 200) <= 5 and abs(cy - 200) <= 5


def test_unreadable_image_is_none(tmp_path):
    bad = tmp_path / "nope.png"
    bad.write_bytes(b"not an image")
    result = detect_markers([str(bad)], dict_id=1)
    assert result["nope.png"] is None
