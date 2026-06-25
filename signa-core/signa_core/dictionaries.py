# SPDX-License-Identifier: MIT
"""ArUco dictionary and detector-parameter helpers (OpenCV-version compatible).

Pure OpenCV/numpy — no WebODM/Django. These are the shared, reusable detection
primitives extracted from the Signa WebODM plugin's self-contained worker
detector, so other consumers (e.g. Mensura's scale calibration) can reuse the
exact same detection behaviour without duplicating it.

The OpenCV ArUco API changed across versions (4.6 vs 4.7+); every helper here
handles both the legacy free-function form and the newer object-oriented form.
"""

# Single source of truth for the offered ArUco dictionaries, as (value, label)
# pairs. Ids 0..20 are OpenCV's predefined dictionaries; 99 is a legacy custom
# 3x3 dictionary built with extendDictionary for existing Signa marker sheets.
DICT_CHOICES = [
    ("0", "0 — DICT_4X4_50"),
    ("1", "1 — DICT_4X4_100"),
    ("2", "2 — DICT_4X4_250"),
    ("3", "3 — DICT_4X4_1000"),
    ("4", "4 — DICT_5X5_50"),
    ("5", "5 — DICT_5X5_100"),
    ("6", "6 — DICT_5X5_250"),
    ("7", "7 — DICT_5X5_1000"),
    ("8", "8 — DICT_6X6_50"),
    ("9", "9 — DICT_6X6_100"),
    ("10", "10 — DICT_6X6_250"),
    ("11", "11 — DICT_6X6_1000"),
    ("12", "12 — DICT_7X7_50"),
    ("13", "13 — DICT_7X7_100"),
    ("14", "14 — DICT_7X7_250"),
    ("15", "15 — DICT_7X7_1000"),
    ("16", "16 — DICT_ARUCO_ORIGINAL"),
    ("17", "17 — DICT_APRILTAG_16h5"),
    ("18", "18 — DICT_APRILTAG_25h9"),
    ("19", "19 — DICT_APRILTAG_36h10"),
    ("20", "20 — DICT_APRILTAG_36h11"),
    ("99", "99 — legacy custom 3×3"),
]

VALID_DICTS = {int(value) for value, _label in DICT_CHOICES}


def load_aruco():
    """Return ``(cv2, cv2.aruco)`` or raise a clear error if aruco is missing."""
    import cv2  # noqa: PLC0415 — lazy: keeps import optional for non-detect consumers
    try:
        from cv2 import aruco
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "OpenCV with the ArUco module (cv2.aruco) is required — install "
            "opencv-contrib-python(-headless)."
        ) from exc
    return cv2, aruco


def make_dictionary(dict_id, aruco=None):
    if aruco is None:
        _, aruco = load_aruco()
    dict_id = int(dict_id)
    if dict_id == 99:
        if hasattr(aruco, "extendDictionary"):
            return aruco.extendDictionary(32, 3)
        return aruco.Dictionary_create(32, 3)
    if hasattr(aruco, "getPredefinedDictionary"):
        return aruco.getPredefinedDictionary(dict_id)
    return aruco.Dictionary_get(dict_id)


def make_parameters(minrate, ignore, aruco=None):
    if aruco is None:
        _, aruco = load_aruco()
    if hasattr(aruco, "DetectorParameters"):
        params = aruco.DetectorParameters()
    else:
        params = aruco.DetectorParameters_create()
    params.minMarkerPerimeterRate = float(minrate)
    params.perspectiveRemoveIgnoredMarginPerCell = float(ignore)
    return params


def make_detector(dictionary, params, aruco=None):
    """Return ``detect(gray) -> (corners, ids, rejected)`` across OpenCV versions."""
    if aruco is None:
        _, aruco = load_aruco()
    if hasattr(aruco, "ArucoDetector"):
        detector = aruco.ArucoDetector(dictionary, params)
        return lambda gray: detector.detectMarkers(gray)
    return lambda gray: aruco.detectMarkers(gray, dictionary, parameters=params)
