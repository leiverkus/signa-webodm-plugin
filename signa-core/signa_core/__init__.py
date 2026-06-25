# SPDX-License-Identifier: MIT
"""signa-core — reusable ArUco marker detection for the Evidentia pipeline.

GUI-/WebODM-free OpenCV detection shared by the Signa WebODM plugin (GCP
detection) and Mensura (metric scale calibration).
"""
from .detect import corner_center, detect_markers, prepare_image
from .dictionaries import (
    DICT_CHOICES,
    VALID_DICTS,
    load_aruco,
    make_detector,
    make_dictionary,
    make_parameters,
)

__version__ = "0.1.0"

__all__ = [
    "detect_markers",
    "corner_center",
    "prepare_image",
    "make_dictionary",
    "make_parameters",
    "make_detector",
    "load_aruco",
    "DICT_CHOICES",
    "VALID_DICTS",
    "__version__",
]
