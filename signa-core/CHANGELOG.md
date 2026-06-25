# Changelog

All notable changes to **signa-core** are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this package adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-06-25

### Added
- **`sheet_layout(page_key, marker_mm, base_id, margin_mm)`** and
  **`compose_sheet_page(...)`** for printable multi-marker control sheets: four
  markers near the page corners at a known fixed spacing (a scale frame).
  `sheet_layout` is the single source of truth for the marker positions, shared
  by the printer and the scaler. `draw_caption` stamps a small config line.
  Enables Mensura's scale-sheet method.

## [0.2.2] - 2026-06-25

### Added
- `compose_page` / `draw_labels` take optional `id_height_mm` and `meta_mm` to
  cap the printed id-number and meta-line text size. Defaults are unchanged
  (Signa's large, standing-height-readable labels); Mensura passes small values
  for close-range markers.

## [0.2.1] - 2026-06-25

### Fixed
- Lowered `requires-python` from `>=3.10` to `>=3.9` so the package installs
  inside WebODM (its webapp/worker run Python 3.9). The code uses no 3.10+
  syntax; the stricter floor blocked the Mensura plugin's `requirements.txt`
  install in WebODM ("No matching distribution found for signa-core").

## [0.2.0] - 2026-06-25

### Added
- `signa_core.markers` — reusable, GUI-free marker-sheet rendering primitives,
  extracted from the Signa plugin's `marker_pdf.py` so both Signa (fit-to-page
  GCP markers) and Mensura (exact-mm scale markers) share one implementation:
  marker raster generation, center aiming aids, label drawing (Pillow primary,
  OpenCV/Hershey fallback), a per-page detectability self-check, `compose_page`,
  a minimal built-in PDF writer (`pages_to_pdf`), and the shared geometry tables
  (`PAGE_SIZES_MM`, `MARKER_AIDS`, `DICT_CAPACITY`, `DICT_LABELS`).
- Optional `labels` extra (`signa-core[labels]`) pulling in Pillow; without it,
  label rendering falls back to OpenCV's Hershey font.

## [0.1.0] - 2026-06-25

### Added
- Initial release: GUI-/WebODM-free ArUco detection core (`detect_markers`,
  dictionary/parameter/detector helpers, `DICT_CHOICES`/`VALID_DICTS`).
