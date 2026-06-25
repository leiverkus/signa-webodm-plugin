# SPDX-License-Identifier: MIT
"""Reusable ArUco marker detection (GUI-free, OpenCV).

The function mirrors the detection behaviour of the Signa WebODM plugin's
self-contained worker detector, but as a normal importable module so consumers
like Mensura (scale calibration) can reuse it. It returns per-image marker
detections (id, corners, center) and leaves the *interpretation* of those
markers — GCP matching (Signa) vs. metric scaling (Mensura) — to the caller.
"""
import os

from .dictionaries import load_aruco, make_detector, make_dictionary, make_parameters


def prepare_image(frame, cv2, enhance_contrast=True):
    """BGR frame -> grayscale, with an optional conservative equalization pass."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    if enhance_contrast and hasattr(cv2, "equalizeHist"):
        return cv2.equalizeHist(gray)
    return gray


def corner_center(corner_set):
    """Mean of a marker's four corners as integer pixel coordinates."""
    import numpy as np
    pts = np.asarray(corner_set, dtype=float).reshape(-1, 2)
    return (
        int(round(float(np.mean(pts[:, 0])))),
        int(round(float(np.mean(pts[:, 1])))),
    )


def detect_markers(image_paths, *, dict_id=1, minrate=0.01, ignore=0.33, adjust=True):
    """Detect ArUco markers across one or more images.

    Parameters mirror the Signa detector: ``dict_id`` selects the ArUco
    dictionary (see ``DICT_CHOICES``), ``minrate`` is the minimum marker
    perimeter rate, ``ignore`` the ignored-margin-per-cell, ``adjust`` toggles
    grayscale equalization.

    Returns ``{image_basename: detections}`` where ``detections`` is a list of
    ``{'id': int, 'corners': [[x, y], ...4], 'center': (x, y)}`` — or ``None``
    for an unreadable image.
    """
    cv2, aruco = load_aruco()
    dictionary = make_dictionary(dict_id, aruco)
    detect = make_detector(dictionary, make_parameters(minrate, ignore, aruco), aruco)

    results = {}
    for path in image_paths:
        frame = cv2.imread(path)
        base = os.path.basename(path)
        if frame is None:
            results[base] = None
            continue
        gray = prepare_image(frame, cv2, adjust)
        corners, ids, _ = detect(gray)
        dets = []
        if ids is not None:
            for i in range(len(ids)):
                marker_id = int(ids[i][0])
                pts = corners[i].reshape(-1, 2)
                dets.append({
                    "id": marker_id,
                    "corners": pts.tolist(),
                    "center": corner_center(corners[i]),
                })
        results[base] = dets
    return results
