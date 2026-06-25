# signa-core

**Reusable, GUI-free ArUco marker detection for the Evidentia pipeline.**

`signa-core` is the pure OpenCV/numpy detection layer extracted from the
[Signa WebODM plugin](../README.md). It detects ArUco markers in images and
returns their ids, corners and centers — leaving the *interpretation* to the
caller:

- **Signa** (WebODM plugin) matches markers against surveyed coordinates → `gcp_list.txt`.
- **Mensura** matches markers against their known physical size → metric scale constraints.

Both share this one detection implementation instead of duplicating it (or
depending on `find-gcp`).

## Install / use

```bash
pip install signa-core   # or: pip install -e signa-core
```

```python
from signa_core import detect_markers

# dict_id 1 = DICT_4X4_100 (see DICT_CHOICES)
result = detect_markers(["img1.jpg", "img2.jpg"], dict_id=1, minrate=0.01, ignore=0.33)
# {'img1.jpg': [{'id': 7, 'corners': [[x, y], ...4], 'center': (cx, cy)}, ...], ...}
```

## Licence

**MIT** — `signa-core` is the permissive, reusable core. The surrounding
**Signa WebODM plugin is AGPL-3.0** (WebODM-forced). This split mirrors the
Itinera pattern (MIT core + copyleft plugin).

## Note on the Signa worker

WebODM runs Signa's GCP detection by serializing a single self-contained
function into a Celery worker, so the plugin keeps its own inlined copy of the
detection primitive for that path. `signa-core` is the canonical, importable
version for all non-worker consumers; the two are kept behaviourally identical.

## Releasing (PyPI)

Published via **PyPI Trusted Publishing** (OIDC) — no API token is stored. See
[`.github/workflows/publish-signa-core.yml`](../.github/workflows/publish-signa-core.yml)
and its header for the one-time pypi.org publisher setup. To release:

```bash
# bump version in pyproject.toml, then:
git tag signa-core-v0.1.0 && git push origin signa-core-v0.1.0
```

The workflow runs the tests, builds the sdist + wheel, and publishes them.
